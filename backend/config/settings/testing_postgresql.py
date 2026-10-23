"""Fast tests on a newly named PostgreSQL database; never reuse an existing test database."""
from copy import deepcopy
from uuid import uuid4

from .testing import *  # noqa: F403
from .base import DATABASES as POSTGRES_DATABASES

DATABASES = deepcopy(POSTGRES_DATABASES)
DATABASES["default"]["TEST"] = {"NAME": f"test_pawconnect_{uuid4().hex[:16]}"}
