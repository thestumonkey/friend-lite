*** Settings ***
Documentation    Conversation Management Keywords
Library          RequestsLibrary
Library          Collections
Library          Process
Library          String
Resource         session_resources.robot
Resource         audio_keywords.robot


*** Keywords ***

Get User Conversations
    [Documentation]    Get conversations for authenticated user (uses admin session)

    ${response}=    GET On Session    api    /api/conversations    expected_status=200
    RETURN    ${response.json()}[conversations]

Get Conversation By ID
    [Documentation]    Get a specific conversation by ID
    [Arguments]       ${conversation_id}
    ${response}=    GET On Session    api    /api/conversations/${conversation_id} 
    RETURN    ${response.json()}[conversation]

Get Conversation Versions
    [Documentation]    Get version history for a conversation
    [Arguments]    ${conversation_id}
    ${response}=    GET On Session    api    /api/conversations/${conversation_id}/versions 
    RETURN    ${response.json()}[transcript_versions]

Get conversation memory versions
    [Documentation]    Get memory version history for a conversation
    [Arguments]    ${conversation_id}
    ${response}=    GET On Session    api    /api/conversations/${conversation_id}/versions/memory
    RETURN    ${response.json()}[memory_versions]

Reprocess Transcript
    [Documentation]    Trigger transcript reprocessing for a conversation
    [Arguments]     ${conversation_id}

    ${response}=    POST On Session    api    /api/conversations/${conversation_id}/reprocess-transcript    expected_status=200

    ${reprocess_data}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${reprocess_data}    job_id
    Dictionary Should Contain Key    ${reprocess_data}    status

    ${job_id}=    Set Variable    ${reprocess_data}[job_id]
    ${initial_status}=    Set Variable    ${reprocess_data}[status]

    Log    Reprocess job created: ${job_id} with status: ${initial_status}    INFO
    Should Be True    '${initial_status}' in ['queued', 'processing']    Status should be 'queued' or 'processing', got: ${initial_status}

    RETURN    ${response.json()}

Reprocess Memory
    [Documentation]    Trigger memory reprocessing for a conversation
    [Arguments]    ${conversation_id}    ${transcript_version_id}=active
    &{params}=     Create Dictionary    transcript_version_id=${transcript_version_id}

    ${response}=    POST On Session    api    /api/conversations/${conversation_id}/reprocess-memory        params=${params}
    RETURN    ${response.json()}

Activate Transcript Version
    [Documentation]    Activate a specific transcript version
    [Arguments]    ${conversation_id}    ${version_id}

    ${response}=    POST On Session    api    /api/conversations/${conversation_id}/activate-transcript/${version_id}  
    RETURN    ${response.json()}

Activate Memory Version
    [Documentation]    Activate a specific memory version
    [Arguments]     ${conversation_id}    ${version_id}

    ${response}=    POST On Session    api    /api/conversations/${conversation_id}/activate-memory/${version_id}  
    RETURN    ${response.json()}

Delete Conversation
    [Documentation]    Delete a conversation
    [Arguments]     ${audio_uuid}

    ${response}=    DELETE On Session    api    /api/conversations/${audio_uuid}    headers=${headers}
    RETURN    ${response.json()}

Delete Conversation Version
    [Documentation]    Delete a specific version from a conversation
    [Arguments]     ${conversation_id}    ${version_type}    ${version_id}

    ${response}=    DELETE On Session    api    /api/conversations/${conversation_id}/versions/${version_type}/${version_id}    headers=${headers}
    RETURN    ${response.json()}

Close Current Conversation
    [Documentation]    Close the current conversation for a client
    [Arguments]    ${client_id}

    ${response}=    POST On Session    api    /api/conversations/${client_id}/close    headers=${headers}
    RETURN    ${response.json()}

Get Cropped Audio Info
    [Documentation]    Get cropped audio information for a conversation
    [Arguments]     ${audio_uuid}

    ${response}=    GET On Session    api    /api/conversations/${audio_uuid}/cropped    headers=${headers}
    RETURN    ${response.json()}[cropped_audios]    

Add Speaker To Conversation
    [Documentation]    Add a speaker to the speakers_identified list
    [Arguments]    ${audio_uuid}    ${speaker_id}
    &{params}=     Create Dictionary    speaker_id=${speaker_id}

    ${response}=    POST On Session    api    /api/conversations/${audio_uuid}/speakers    headers=${headers}    params=${params}
    RETURN    ${response.json()}

Update Transcript Segment
    [Documentation]    Update a specific transcript segment
    [Arguments]    ${audio_uuid}    ${segment_index}    ${speaker_id}=${None}    ${start_time}=${None}    ${end_time}=${None}
    &{params}=     Create Dictionary

    IF    '${speaker_id}' != '${None}'
        Set To Dictionary    ${params}    speaker_id=${speaker_id}
    END
    IF    '${start_time}' != '${None}'
        Set To Dictionary    ${params}    start_time=${start_time}
    END
    IF    '${end_time}' != '${None}'
        Set To Dictionary    ${params}    end_time=${end_time}
    END

    ${response}=    PUT On Session    api    /api/conversations/${audio_uuid}/transcript/${segment_index}    headers=${headers}    params=${params}
    RETURN    ${response.json()}


Create Test Conversation
    [Documentation]    Create a test conversation by processing a test audio file
    [Arguments]     ${device_name}=test-device

    # Upload test audio file to create a conversation

    ${conversation}=    Upload Audio File     ${TEST_AUDIO_FILE}    ${device_name}

    RETURN    ${conversation}

Verify Transcript Content
    [Documentation]    Verify transcript contains expected content and quality
    [Arguments]    ${conversation}    ${expected_keywords}    ${min_length}=50

    Dictionary Should Contain Key    ${conversation}    transcript
    ${transcript}=    Set Variable    ${conversation}[transcript]
    Should Not Be Empty    ${transcript}

    # Check length
    ${transcript_length}=    Get Length    ${transcript}
    Should Be True    ${transcript_length} >= ${min_length}    Transcript too short: ${transcript_length}

    # Check for expected keywords
    ${transcript_lower}=    Convert To Lower Case    ${transcript}
    FOR    ${keyword}    IN    @{expected_keywords}
        ${keyword_lower}=    Convert To Lower Case    ${keyword}
        Should Contain    ${transcript_lower}    ${keyword_lower}    Missing keyword: ${keyword}
    END

    # Verify segments exist
    Dictionary Should Contain Key    ${conversation}    segments
    ${segments}=    Set Variable    ${conversation}[segments]
    ${segment_count}=    Get Length    ${segments}
    Should Be True    ${segment_count} > 0    No segments found

    Log    Transcript verification passed: ${transcript_length} chars, ${segment_count} segments    INFO

Find Test Conversation
    [Documentation]    Find the oldest (earliest created) conversation or create one if none exist
    ...                Returns the first conversation in the list, which should be the oldest/fixture
    ${conversations_data}=    Get User Conversations
    Log    Retrieved conversations data: ${conversations_data}

    # conversations_data is now a flat list
    ${count}=    Get Length    ${conversations_data}

    IF    ${count} > 0
        # Sort by created_at to get oldest conversation first (most stable for tests)
        ${sorted_convs}=    Evaluate    sorted($conversations_data, key=lambda x: x.get('created_at', ''))
        ${oldest_conv}=    Set Variable    ${sorted_convs}[0]
        Log    Using oldest conversation (created_at: ${oldest_conv}[created_at])
        RETURN    ${oldest_conv}
    END

    # If no conversations exist, create one by uploading test audio
    Log    No conversations found, creating one by uploading test audio
    ${conversation}=    Upload Audio File    ${TEST_AUDIO_FILE}    ${TEST_DEVICE_NAME}

    # Wait for initial processing to complete
    Sleep    5s

    RETURN    ${conversation}

Create Fixture Conversation
    [Documentation]    Create a persistent fixture conversation for reuse across tests
    ...                This conversation will NOT be deleted between test suites
    ...                Tags the conversation with is_fixture=true in MongoDB
    ...                Audio files will be stored in fixtures/ subfolder
    ...                Returns the conversation ID
    [Arguments]    ${device_name}=fixture-device

    Log To Console    \nCreating fixture conversation...

    # Upload test audio to fixtures folder
    ${conversation}=    Upload Audio File    ${TEST_AUDIO_FILE}    ${device_name}    folder=fixtures

    # Verify conversation was created successfully (MongoDB uses conversation_id as the field name)
    Dictionary Should Contain Key    ${conversation}    conversation_id
    ${conversation_id}=    Set Variable    ${conversation}[conversation_id]

    # Verify it has transcript content
    Dictionary Should Contain Key    ${conversation}    transcript
    ${transcript}=    Set Variable    ${conversation}[transcript]
    Should Not Be Empty    ${transcript}    Fixture conversation has no transcript

    # Tag this conversation as a fixture in MongoDB so cleanup preserves it
    ${result}=    Run Process    docker exec advanced-mongo-test-1 mongosh test_db --eval "db.conversations.updateOne({'conversation_id': '${conversation_id}'}, {\\$set: {'is_fixture': true}})"    shell=True
    Should Be Equal As Integers    ${result.rc}    0    Failed to tag conversation as fixture: ${result.stderr}

    # Also tag audio_chunks
    ${result2}=    Run Process    docker exec advanced-mongo-test-1 mongosh test_db --eval "db.audio_chunks.updateMany({'conversation_id': '${conversation_id}'}, {\\$set: {'is_fixture': true}})"    shell=True
    Should Be Equal As Integers    ${result2.rc}    0    Failed to tag audio chunks as fixture: ${result2.stderr}

    Log To Console    ✓ Audio files stored in fixtures/ subfolder

    ${transcript_len}=    Get Length    ${transcript}
    Log To Console    ✓ Fixture conversation created: ${conversation_id}
    Log To Console    ✓ Transcript length: ${transcript_len} chars
    Log To Console    ✓ Tagged as fixture (is_fixture=true)

    Set Global Variable    ${FIXTURE_CONVERSATION_ID}    ${conversation_id}

    RETURN    ${conversation_id}

Get Fixture Conversation
    [Documentation]    Get the persistent fixture conversation
    ...                Use this in tests that need an existing conversation without creating one
    ...                Returns the full conversation object

    # Check if fixture was created (uses Get Variable Value to avoid errors if not set)
    ${fixture_id}=    Get Variable Value    ${FIXTURE_CONVERSATION_ID}    ${EMPTY}

    IF    '${fixture_id}' == '${EMPTY}'
        Fail    Fixture conversation not created. Call 'Create Fixture Conversation' in suite setup first.
    END

    ${conversation}=    Get Conversation By ID    ${fixture_id}

    RETURN    ${conversation}

Check Conversation Has End Reason
    [Documentation]    Check if conversation has end_reason set (not None)
    [Arguments]    ${conversation_id}

    ${conversation}=    Get Conversation By ID    ${conversation_id}
    ${end_reason}=    Set Variable    ${conversation}[end_reason]
    Should Not Be Equal As Strings    ${end_reason}    None    msg=End reason not set yet
    RETURN    ${conversation}
