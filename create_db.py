# ### CREATE A DB ###

from sqlalchemy import Column, Integer, \
    String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.functions import current_timestamp
from sqlalchemy import create_engine

import config

engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Tokens(Base):
    """ Individual Token data """
    __tablename__ = 'tokens'

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    date_created = Column(
        DateTime,
        default=current_timestamp()
    )

    # Token Bot Session UUID
    session_uuid = Column(String())

    # Creator Details
    creator_username = Column(String())
    creator_pay_addr = Column(String())

    # Token Details
    token_ticker = Column(String(5))
    token_name = Column(String(128))
    token_desc = Column(String(128))
    token_number = Column(Integer, default=0)
    # Added, maybe future use with generic Native Tokens..?
    token_amount = Column(Integer, default=1)
    token_ipfs_hash = Column(String(50))

    def __init__(self, session_uuid):
        self.session_uuid = session_uuid

    def __repr__(self):
        return f"{self.session_uuid} - {self.token_ticker}"

    def update(self, **kwargs):
        """ Updates a Token information  """
        for key, value in kwargs.items():
            setattr(self, key, value)

def main():
    """ Creates the DB with Token table """
    Base.metadata.create_all(engine)
    session = Session()
    session.commit()
    session.close()
    print("Created DB")


if __name__ == '__main__':
    main()
