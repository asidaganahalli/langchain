import typing

ERROR

# It's currently impossible to support mypy for both pydantic v1 and v2 at once:
# https://github.com/pydantic/pydantic/issues/6022
#
# In the lint environment, pydantic is currently v1.
# When we upgrade it to pydantic v2, we'll need
# to replace this with `from pydantic.v1.main import *`.
if typing.TYPE_CHECKING:
    from pydantic.main import *  # noqa: F403
else:
    try:
        from pydantic.v1.main import *  # noqa: F403
    except ImportError:
        from pydantic.main import *  # noqa: F403
