import os, tempfile, pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.document import Base
from app.db.session import get_db
from app.main import app
@pytest.fixture()
def db_session():
    fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
    engine=create_engine(f'sqlite:///{path}', connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    db=Session()
    try: yield db
    finally:
        db.close(); os.remove(path)

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
    engine=create_engine(f'sqlite:///{path}', connect_args={'check_same_thread':False})
    TestingSession=sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    def override():
        db=TestingSession()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db]=override
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear(); os.remove(path)
