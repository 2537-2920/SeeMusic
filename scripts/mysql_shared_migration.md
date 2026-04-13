# MySQL 8.0 Shared-DB Migration (No Elevated Privileges)

This workflow prepares a dump so every developer can import it into a shared MySQL 8.0 database without `SUPER`-level privileges.

## One-click migration with root `.env`

Store your remote settings in the project-root `.env` file:

```dotenv
SSH_HOST=175.24.130.34
SSH_USER=ubuntu
SSH_PORT=22
SSH_KEY_FILE=C:\Users\yourName\.ssh\yourkeyname
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB_NAME=SeeMusic
MYSQL_DUMP_INPUT=SeeMusic
MYSQL_DUMP_OUTPUT=SeeMusic.safe.sql
MYSQL_REMOTE_DIR=/tmp/seemusic_migration
MYSQL_KEEP_REMOTE_FILES=0
MYSQL_SKIP_VERIFY=0
```

Then run:

```bash
python scripts/migrate_mysql_dump.py
```

Notes:
- `MYSQL_USER` is required and should be your real MySQL account, not the SSH login user unless they are intentionally the same.
- If `MYSQL_PASSWORD` is empty, the script prompts for it at runtime.
- Command-line flags still work and override `.env` values when needed.

## 1) Prepare a safe dump locally

From project root:

```bash
python scripts/prepare_mysql_dump.py --input SeeMusic --output SeeMusic.safe.sql
```

What gets removed automatically:
- `SET @@GLOBAL.GTID_PURGED...`
- `LOCK TABLES ...`
- `UNLOCK TABLES`
- `DEFINER=...` clauses (if present)

## 2) Upload dump to remote host

```bash
scp SeeMusic.safe.sql <ssh_user>@<server_ip>:/tmp/SeeMusic.safe.sql
```

## 3) Create database (database-level only)

On remote host:

```bash
mysql -h 127.0.0.1 -P 3306 -u <dev_user> -p < scripts/create_seemusic_db.sql
```

Or run equivalent SQL manually:

```sql
CREATE DATABASE IF NOT EXISTS `SeeMusic`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

## 4) Import data

On remote host:

```bash
mysql -h 127.0.0.1 -P 3306 -u <dev_user> -p SeeMusic < /tmp/SeeMusic.safe.sql
```

## 5) Validate import

```bash
mysql -h 127.0.0.1 -P 3306 -u <dev_user> -p < scripts/verify_seemusic_import.sql
```

Expected:
- `SHOW TABLES` returns app tables
- row counts return values for: `user`, `project`, `sheet`, `report`, `community_post`, `export_record`, `audio_analysis`, `pitch_sequence`, `user_history`

## 6) Shared permission baseline (DBA one-time)

For each developer account, grant database-level privileges only:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP
ON `SeeMusic`.* TO 'dev_user'@'%';
FLUSH PRIVILEGES;
```

No elevated global privileges required.

## 7) Rollback safety

Keep original dump (`SeeMusic`) and generated safe dump (`SeeMusic.safe.sql`) for at least 24 hours after cutover.
