import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt has a 72-byte limit. We truncate to 72 characters to stay safe.
    password_bytes = plain_password[:72].encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def get_password_hash(password: str) -> str:
    # bcrypt has a 72-byte limit. We truncate to 72 characters to stay safe.
    password_bytes = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')
