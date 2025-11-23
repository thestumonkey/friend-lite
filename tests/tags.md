# Robot Framework Test Tags Reference

This document defines the standard tags used across the Friend-Lite test suite.

## Tag Format

**IMPORTANT**: Tags must be **tab-separated**, not space-separated.

```robot
# Correct - tabs between tags
[Tags]    auth	negative

# Incorrect - spaces between tags
[Tags]    auth negative
```

## Core Tags by Category

### Test Type (20 uses)
- `negative` - Error handling, invalid inputs, and failure scenarios

### Security & Access (33 uses)
- `security` (16) - Authentication and authorization tests
- `auth` (5) - Authentication workflows
- `admin` (12) - Admin-only operations

### Core Components (66 uses)
- `system` (15) - System-level operations and configuration
- `queue` (14) - Job queue management (RQ workers, job monitoring)
- `chat` (14) - Chat service and sessions
- `user` (12) - User management and operations
- `conversation` (12) - Conversation management and transcription
- `memory` (11) - Memory extraction, storage, and search

### Processing & Services (28 uses)
- `session` (9) - Session management
- `health` (9) - Health checks and readiness endpoints
- `integration` (6) - End-to-end integration tests
- `speaker` (5) - Speaker recognition and diarization
- `rq` (5) - Redis Queue specific operations

### Technical Features (28 uses)
- `websocket` (4) - WebSocket streaming
- `validation` (4) - Input validation
- `streaming` (4) - Real-time stream processing
- `processing` (4) - Data processing workflows
- `config` (4) - Configuration management
- `statistics` (3) - Statistics and metrics endpoints
- `service` (3) - Service management
- `pagination` (3) - Paginated API responses
- `permissions` (3) - Data isolation and permission tests
- `client` (3) - Client connection management

### Specialized (14 uses)
- `versioning` (2) - Version management for transcripts/memories
- `segment` (2) - Audio segment handling
- `diarization` (2) - Speaker diarization
- `cropping` (2) - Audio cropping
- `audio` (2) - Audio processing

### Single-Use Specialized Tags
These tags are used for very specific test scenarios:
- `upload`, `update`, `crud`, `delete` - CRUD operations
- `todo`, `timeout`, `stress` - Edge cases
- `speech`, `search`, `list` - Specific operations
- `restart`, `reload` - Service management
- `multiple`, `metrics`, `message`, `manager` - Various features
- `invalid`, `inactivity`, `enqueue` - Error scenarios
- `e2e`, `detailed`, `debug` - Test types
- `critical`, `connection`, `close` - System operations
- `active`, `activation`, `accuracy` - State management

## Tag Consolidation Rules

### Prohibited Synonyms
To prevent tag duplication, these terms have been consolidated:

**DO NOT create new tags with these terms:**
- ❌ `positive` - Removed (default assumption)
- ❌ `users` → Use `user` instead
- ❌ `login` → Use `auth` instead
- ❌ `create`, `delete`, `update`, `upload` → Use `crud` if needed, or be specific
- ❌ `version`, `versions` → Use `versioning` instead
- ❌ `stats` → Use `statistics` instead
- ❌ `status`, `readiness` → Use `health` instead
- ❌ `jobs` → Use `queue` instead
- ❌ `reprocess`, `workflow`, `pipeline` → Use `processing` instead
- ❌ `messages` → Use `message` instead
- ❌ `isolation` → Use `permissions` instead
- ❌ `notfound`, `persistence`, `individual` - Removed (too specific)
- ❌ `speed-fast`, `speed-mid`, `speed-long` - Removed (execution time tags not needed)

### When Adding New Tags

Before adding a new tag, check:

1. **Does a similar tag already exist?** Review this document first
2. **Is it a synonym?** Use the consolidated version instead
3. **Is it single-use?** Consider if a more general existing tag would work
4. **Is it descriptive?** Tag should clearly indicate what aspect is being tested

### Tag Naming Guidelines

- **Use lowercase** - All tags are lowercase
- **Be concise** - Single words preferred (e.g., `auth` not `authentication`)
- **Be specific** - But not too specific (avoid test-specific tags)
- **Be consistent** - Check existing tags before creating new ones
- **Prefer nouns** - `memory`, `queue`, `session` not `memorize`, `queuing`
- **Avoid redundancy** - Don't tag with both `auth` and `security` unless both aspects are tested

## Tag Usage Examples

### Good Examples

```robot
# Clear, concise, uses existing tags
[Tags]    auth	negative

# Multiple aspects of a test
[Tags]    conversation	memory	processing

# Security test for admin endpoints
[Tags]    admin	security	negative
```

### Bad Examples

```robot
# DON'T use spaces between tags
[Tags]    auth negative

# DON'T create synonyms
[Tags]    authentication	login	users

# DON'T use overly specific tags
[Tags]    test_login_with_invalid_email_format

# DON'T use positive (implied)
[Tags]    auth	positive
```

## Updating This Document

When you add, remove, or consolidate tags:

1. Update the relevant section above
2. Update the "Prohibited Synonyms" section if needed
3. Update tag counts if they change significantly
4. Commit changes with a clear message explaining the tag changes

---

**Last Updated:** 2025-01-23
**Total Unique Tags:** ~60 (after consolidation)
