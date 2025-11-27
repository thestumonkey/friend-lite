import io
import time
import os
import argparse
import math
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from lib.resources import call_resource
from lib.worker import setup_worker_logging, get_worker_id, mongo_cursor, claim_chunks, release_chunks

logger = setup_worker_logging('diarization_worker')

from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from datetime import timedelta
from typing import Any, Iterator, Optional
from pytz import UTC

import signal

signal.signal(signal.SIGINT, signal.SIG_DFL)

DIARIZATION_SERVER_URL = os.environ.get('DIARIZATION_SERVER_URL', 'http://localhost:8085').rstrip('/')

import numpy as np
from chunking import read_codec, array_to_wav, sample_rate


class DiarizationSequence(BaseModel):
    original_id: ObjectId
    chunks: list[Any] = []
    is_partial: bool = False
    is_continuation: bool = False

    class Config:
        arbitrary_types_allowed = True

    @property
    def last(self) -> Any:
        return self.chunks[-1]

    @property
    def start(self) -> datetime:
        return self.chunks[0]['start'] if self.chunks else datetime.now(tz=UTC)

    @property
    def min_index(self) -> int:
        return self.chunks[0]['index'] if self.chunks else 0

    @property
    def max_index(self) -> int:
        return self.last['index']

    def __repr__(self):
        indices = [chunk['index'] for chunk in self.chunks]
        return f'{self.original_id}: {repr(indices)}'



def _build_pending_chunk_filters(filters: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    base_filters: dict[str, Any] = {
        '$and': [
            {
                '$or': [
                    {'diarized_at': {'$exists': False}},
                    {'diarized_at': None}
                ]
            },
            {
                '$or': [
                    {'processing_by': {'$exists': False}},
                    {'processing_by': None}
                ]
            },
            {'vad.has_speech': True}
        ]
    }

    if filters:
        base_filters.update(filters)

    return base_filters


def count_pending_chunks(filters: Optional[dict[str, Any]] = None) -> Optional[int]:
    """
    Count audio chunks that still need diarization.
    """
    query = _build_pending_chunk_filters(filters)
    result = call_resource('tech.mycelia.mongo', {
        "action": "count",
        "collection": "audio_chunks",
        "query": query
    })
    return int(result) if result is not None else None


def _format_eta(seconds: Optional[float]) -> str:
    if seconds is None or not math.isfinite(seconds) or seconds <= 0:
        return 'n/a'
    return str(timedelta(seconds=int(seconds)))



def get_diarization_sequences(limit=10, filters=None, max_sequence_length=30, worker_id=None) -> Iterator[DiarizationSequence]:
    sequences_by_id: dict[ObjectId, DiarizationSequence] = {}
    yielded = 0

    base_filters = _build_pending_chunk_filters(filters)

    for chunk in mongo_cursor('audio_chunks', base_filters, {
        "sort": {"start": 1},  # Sort ascending to get consecutive chunks
    }):
        if limit is not None and yielded >= limit:
            break

        original_id = chunk['original_id']
        start = chunk['start']

        # Clean up old sequences that are too far in the past
        for existing_id, seq in tuple(sequences_by_id.items()):
            if start - seq.start > timedelta(seconds=600):
                if not seq.is_continuation or len(seq.chunks) > 1:
                    yield seq
                    yielded += 1
                del sequences_by_id[existing_id]

        seq = sequences_by_id.get(original_id)

        # If sequence exists but chunk index is not consecutive, yield the sequence and start new one
        if seq and seq.max_index + 1 != chunk['index']:
            assert chunk not in seq.chunks
            yield seq
            yielded += 1
            del sequences_by_id[original_id]
            seq = None

        if original_id not in sequences_by_id:
            try:
                seq = sequences_by_id[original_id] = DiarizationSequence(
                    original_id=original_id,
                    chunks=[]
                )
            except Exception as e:
                tqdm.write(f"ERROR: Creating diarization sequence for {original_id}: {e}")
                continue

        seq.chunks.append(chunk)

        # If we've reached max sequence length, yield it and create continuation
        if len(seq.chunks) >= max_sequence_length:
            seq.is_partial = True
            yield seq
            yielded += 1
            sequences_by_id[original_id] = DiarizationSequence(
                original_id=original_id,
                chunks=[chunk],
                is_continuation=True,
            )

    # Yield remaining sequences
    if limit is None or yielded < limit:
        for seq in sequences_by_id.values():
            yield seq


def combine_chunks_to_wav(sequence: DiarizationSequence) -> io.BytesIO:
    """
    Combine opus chunks into a single WAV file.
    Handles gaps between chunks by inserting silence.
    """
    audio_arrays = []
    current_time = sequence.start

    for chunk in sequence.chunks:
        # Decode opus chunk to numpy array
        audio = read_codec(chunk['data'], codec="opus", sample_rate=sample_rate)
        chunk_duration = timedelta(seconds=len(audio) / sample_rate)

        # Calculate gap between expected time and actual chunk start
        gap = (chunk['start'] - current_time).total_seconds()

        if gap > 0:
            # Insert silence for gap
            silence_samples = int(gap * sample_rate)
            audio_arrays.append(np.zeros(silence_samples, dtype=np.float32))
        elif gap < 0:
            # Overlap - truncate previous audio or handle overlap
            overlap_samples = int(-gap * sample_rate)
            if audio_arrays and len(audio_arrays[-1]) > overlap_samples:
                audio_arrays[-1] = audio_arrays[-1][:-overlap_samples]

        audio_arrays.append(audio)
        current_time = chunk['start'] + chunk_duration

    # Concatenate all audio arrays
    combined_audio = np.concatenate(audio_arrays, axis=0)

    # Convert to WAV
    return array_to_wav(combined_audio, sample_rate=sample_rate)


def claim_sequence(seq: DiarizationSequence, worker_id: str) -> bool:
    chunk_ids = [chunk['_id'] for chunk in seq.chunks]
    success = claim_chunks(chunk_ids, worker_id)

    if not success:
        release_sequence(seq, worker_id)

    return success


def release_sequence(seq: DiarizationSequence, worker_id: str):
    chunk_ids = [chunk['_id'] for chunk in seq.chunks]
    release_chunks(chunk_ids, worker_id)


def diarize_sequence(sequence: DiarizationSequence, worker_id: str):
    """
    Combine chunks to WAV, call diarization API, and save results to MongoDB.
    """
    start_time = time.time()
    timestamp = sequence.start.strftime("%Y-%m-%d %H:%M:%S")
    chunks_count = len(sequence.chunks)
    chunks_marked = 0
    original_id = str(sequence.original_id)

    try:
        if not claim_sequence(sequence, worker_id):
            tqdm.write(f'{timestamp}  {chunks_count:3d} chunks  {original_id}  skipped (claimed)')
            return {"status": "skipped", "chunks": 0, "chunks_diarized": 0, "duration": 0, "segments": 0}

        # Combine chunks into WAV file
        wav_file = combine_chunks_to_wav(sequence)
        wav_file.seek(0)

        # Call diarization API
        response = requests.post(
            f'{DIARIZATION_SERVER_URL}/diarize',
            files={'file': ('audio.wav', wav_file, 'audio/wav')},
            timeout=300 + len(sequence.chunks) * 3
        )
        response.raise_for_status()

        data = response.json()
        segments = data.get('segments', [])

        if not segments:
            # No segments found, mark as processed
            chunks_marked = mark_as_diarized(sequence)
            end_time = time.time()
            duration = end_time - start_time
            tqdm.write(f'{timestamp}  {chunks_count:3d} chunks  {original_id}  {duration:5.2f}s  no_segments')
            return {
                "status": "no_segments",
                "chunks": chunks_count,
                "chunks_diarized": chunks_marked,
                "duration": duration,
                "segments": 0
            }

        # Generate unique inference_id for this diarization run
        inference_id = ObjectId()
        sequence_start_time = sequence.start

        # Save each segment as a separate document
        saved_segments = 0
        for segment in segments:
            # Convert relative times to absolute datetimes
            segment_start_relative = segment['start']  # seconds relative to audio start
            segment_end_relative = segment['end']  # seconds relative to audio start

            # Calculate absolute start time (sequence start + relative offset)
            segment_start_absolute = sequence_start_time + timedelta(seconds=segment_start_relative)
            segment_end_absolute = sequence_start_time + timedelta(seconds=segment_end_relative)

            # Save segment to diarizations collection
            call_resource('tech.mycelia.mongo', {
                "action": "insertOne",
                "collection": "diarizations",
                "doc": {
                    "inference_id": inference_id,
                    "original_id": sequence.original_id,
                    "start": segment_start_absolute,
                    "end": segment_end_absolute,
                    "speaker": segment['speaker'],
                    "embedding": segment['embedding'],  # 256 floats
                    "duration": segment.get('duration', segment_end_relative - segment_start_relative),
                    "created_at": datetime.now(tz=UTC)
                }
            })
            saved_segments += 1

        # Mark chunks as diarized
        chunks_marked = mark_as_diarized(sequence)

        end_time = time.time()
        duration = end_time - start_time
        tqdm.write(f'{timestamp}  {chunks_count:3d} chunks  {original_id}  {duration:5.2f}s  diarized  {saved_segments} segments')
        return {
            "status": "diarized",
            "chunks": chunks_count,
            "chunks_diarized": chunks_marked,
            "duration": duration,
            "segments": saved_segments
        }

    except requests.exceptions.ReadTimeout:
        end_time = time.time()
        release_sequence(sequence, worker_id)
        tqdm.write(f'{timestamp}  {chunks_count:3d} chunks  {original_id}  ERROR: ReadTimeout')
        tqdm.write(f'  → Increase timeout or check diarization server at {DIARIZATION_SERVER_URL}')
        return {
            "status": "error",
            "chunks": 0,
            "chunks_diarized": 0,
            "duration": end_time - start_time,
            "segments": 0
        }

    except Exception as e:
        end_time = time.time()
        release_sequence(sequence, worker_id)
        tqdm.write(f'{timestamp}  {chunks_count:3d} chunks  {original_id}  ERROR: {str(e)}')
        return {
            "status": "error",
            "chunks": 0,
            "chunks_diarized": 0,
            "duration": end_time - start_time,
            "segments": 0
        }


def mark_as_diarized(seq: DiarizationSequence) -> int:
    """
    Mark chunks as diarized by setting diarized_at timestamp.
    For partial sequences, mark all but the last chunk.
    """
    chunks_to_mark = seq.chunks[:-1] if seq.is_partial else seq.chunks
    if not chunks_to_mark:
        return 0

    call_resource('tech.mycelia.mongo', {
        "action": "updateMany",
        "collection": "audio_chunks",
        "query": {
            '_id': {'$in': [chunk['_id'] for chunk in chunks_to_mark]},
        },
        "update": {
            '$set': {'diarized_at': datetime.now(tz=UTC)},
        }
    })
    return len(chunks_to_mark)


def process_sequence(sequence: DiarizationSequence, worker_id: str):
    """Wrapper for diarize_sequence to match stt.py pattern."""
    return diarize_sequence(sequence, worker_id)


def process_diarization_sequences(limit=None, max_workers=1, worker_id=None):
    if worker_id is None:
        worker_id = get_worker_id()

    tqdm.write(f'Worker ID: {worker_id}')
    tqdm.write(f'Using {max_workers} parallel worker(s)')
    tqdm.write(f'Diarization server: {DIARIZATION_SERVER_URL}')

    pending_chunks_total: Optional[int] = None
    try:
        pending_chunks_total = count_pending_chunks()
    except Exception as exc:
        tqdm.write(f'Pending chunk count unavailable: {exc}')
    else:
        if pending_chunks_total is not None:
            tqdm.write(f'Pending chunks: {pending_chunks_total}')
        else:
            tqdm.write('Pending chunk count unavailable')

    processed_count = 0
    stats = {'diarized': 0, 'no_segments': 0, 'error': 0, 'skipped': 0}
    sequence_chunks_total = 0
    completed_chunks = 0
    total_segments = 0
    batch_size = min(limit if limit else 1000, 1000)
    run_start_time = time.time()

    total = limit if limit else None
    bar_format = '{n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}, {postfix}]' if total else '{n_fmt} [{elapsed}, {rate_fmt}, {postfix}]'

    with tqdm(total=total, desc="Processing", unit="seq", bar_format=bar_format) as pbar:

        def record_result(result: dict[str, Any]) -> bool:
            nonlocal processed_count, sequence_chunks_total, completed_chunks, total_segments
            status = result["status"]

            if status in stats:
                stats[status] += 1

            sequence_chunks_total += result.get("chunks", 0)
            total_segments += result.get("segments", 0)
            completed_chunks += result.get("chunks_diarized", 0)

            counted = status != "skipped"
            if counted:
                processed_count += 1

            pbar.update(1)

            elapsed = max(time.time() - run_start_time, 0.0)
            chunk_rate = (completed_chunks / elapsed) if completed_chunks and elapsed > 0 else None
            remaining_chunks = None
            if pending_chunks_total is not None:
                remaining_chunks = max(pending_chunks_total - completed_chunks, 0)
            eta_seconds = (remaining_chunks / chunk_rate) if chunk_rate and remaining_chunks is not None and chunk_rate > 0 else None
            chunk_target_display = pending_chunks_total if pending_chunks_total is not None else '?'
            chunk_display = f"{completed_chunks}/{chunk_target_display}"

            pbar.set_postfix(
                diarized=stats['diarized'],
                no_segments=stats['no_segments'],
                errors=stats['error'],
                skipped=stats['skipped'],
                chunks=chunk_display,
                rate=f"{chunk_rate:.1f}/s" if chunk_rate else 'n/a',
                eta=_format_eta(eta_seconds),
                segments=total_segments
            )

            return counted

        if max_workers == 1:
            while True:
                batch_processed = 0
                for sequence in get_diarization_sequences(limit=batch_size, worker_id=worker_id):
                    result = process_sequence(sequence, worker_id)
                    if record_result(result):
                        batch_processed += 1

                    if limit and processed_count >= limit:
                        break

                if limit and processed_count >= limit:
                    break

                if batch_processed == 0:
                    tqdm.write("\nNo more sequences to process")
                    break
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while True:
                    sequences = list(get_diarization_sequences(limit=batch_size, worker_id=worker_id))
                    if not sequences:
                        tqdm.write("\nNo more sequences to process")
                        break

                    futures = {executor.submit(process_sequence, seq, worker_id): seq for seq in sequences}

                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        record_result(result)

                        if limit and processed_count >= limit:
                            break

                    if limit and processed_count >= limit:
                        break

    tqdm.write("\n" + "=" * 80)
    tqdm.write(f"Completed: {processed_count} sequences, {completed_chunks} chunks, {total_segments} segments")
    tqdm.write(f"Stats: diarized={stats['diarized']}, no_segments={stats['no_segments']}, errors={stats['error']}, skipped={stats['skipped']}")
    tqdm.write("=" * 80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    process_diarization_sequences(limit=args.limit, max_workers=1)
