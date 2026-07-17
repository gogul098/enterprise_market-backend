"""
SQLAlchemy engine with connection pooling and session factory for MariaDB / InnoDB.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sshtunnel import SSHTunnelForwarder

from backend.config import settings

# ── Auto-Start SSH Tunnel for AWS RDS ────────────────────────────────────────
db_url = settings.DATABASE_URL
try:
    db_host_ip = "13.233.147.145"
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pem_file = os.path.join(base_dir, 'LambdaFinancials.pem')
    
    # Render Support: Write PEM file from environment variable if it doesn't exist
    if not os.path.exists(pem_file) and os.getenv("SSH_PEM_KEY"):
        import tempfile
        pem_file = os.path.join(tempfile.gettempdir(), 'render_ssh.pem')
        with open(pem_file, "w") as f:
            # Replace literal \n with actual newlines
            f.write(os.getenv("SSH_PEM_KEY").replace("\\n", "\n"))
        os.chmod(pem_file, 0o400) # Required for SSH keys

    if os.path.exists(pem_file) and "127.0.0.1" in settings.DATABASE_URL:
        # Start tunnel on an ephemeral/free port
        tunnel = SSHTunnelForwarder(
            (db_host_ip, 22),
            ssh_username='ubuntu',
            ssh_pkey=pem_file,
            remote_bind_address=('127.0.0.1', 3306)
        )
        tunnel.start()
        # Override the database URL with the dynamically assigned local port
        db_url = db_url.replace("127.0.0.1:3306", f"127.0.0.1:{tunnel.local_bind_port}")
        print(f"[*] SSH Tunnel started successfully on 127.0.0.1:{tunnel.local_bind_port}")
except Exception as e:
    print(f"[!] Warning: SSH Tunnel failed to start. Error: {e}")
    if os.getenv("SSH_PEM_KEY"):
        # If we are on Render and it failed, crash loudly so we can see the exact SSH error
        raise RuntimeError(f"SSH Tunnel failed to start on Render: {e}") from e

engine = create_engine(
    db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # Reconnect stale connections automatically
    pool_recycle=3600,         # Recycle connections every hour
    isolation_level="READ COMMITTED",  # Prevent MariaDB error 1020 on concurrent SELECT ... FOR UPDATE
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
