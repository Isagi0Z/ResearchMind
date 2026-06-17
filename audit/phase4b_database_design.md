# Phase 4B Database Schema Design

## Evaluation of PostgreSQL Entities

### Users
- id: UUID (Primary Key)
- username: VARCHAR(255) (Unique)
- email: VARCHAR(255) (Unique)
- password_hash: VARCHAR(255)
- ole: VARCHAR(50)
- created_at: TIMESTAMP (Default UTC NOW)
- updated_at: TIMESTAMP
- is_active: BOOLEAN (Default TRUE)

### Queries
- id: UUID (Primary Key)
- user_id: UUID (Foreign Key -> Users.id)
- aw_query: TEXT
- query_type: VARCHAR(100)
- esult: JSONB (Stores structured outputs and traces)
- created_at: TIMESTAMP

### Reviews
- id: UUID (Primary Key)
- user_id: UUID (Foreign Key -> Users.id)
- 	itle: VARCHAR(255)
- eview_result: JSONB (Synthesized output)
- metadata: JSONB
- created_at: TIMESTAMP

### Documents
- id: UUID (Primary Key)
- ingerprint: VARCHAR(255) (Unique hash)
- 	itle: VARCHAR(1024)
- metadata: JSONB
- created_at: TIMESTAMP

### Tokens / Sessions
- Refresh token rotation model.
- id: UUID
- user_id: UUID (Foreign Key)
- efresh_token: VARCHAR (Hashed)
- expires_at: TIMESTAMP
- is_revoked: BOOLEAN

## Relationships
- A User has many Queries.
- A User has many Reviews.
- Documents are uniquely fingerprinted, potentially linked via many-to-many to Corpora (if Corpus entity is added later).
