import asyncio
import time
import urllib.request
import uuid
import pytest
from enum import Enum
from urllib.error import HTTPError

from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent_toolkits.ainetwork.toolkit import AINetworkToolkit
from langchain.chat_models import ChatOpenAI
from langchain.tools.ainetwork.utils import authenticate


class Match(Enum):
    __test__ = False
    ListWildcard = 1
    StrWildcard = 2
    DictWildcard = 3
    IntWildcard = 4
    FloatWildcard = 5
    ObjectWildcard = 6

    @classmethod
    def __eq__(cls, value, template):
        if template is cls.ListWildcard:
            return isinstance(value, list)
        elif template is cls.StrWildcard:
            return isinstance(value, str)
        elif template is cls.DictWildcard:
            return isinstance(value, dict)
        elif template is cls.IntWildcard:
            return isinstance(value, int)
        elif template is cls.FloatWildcard:
            return isinstance(value, float)
        elif template is cls.ObjectWildcard:
            return True
        elif type(value) != type(template):
            return False
        elif isinstance(value, dict):
            if len(value) != len(template):
                return False
            for k, v in value.items():
                if k not in template or not cls.__eq__(v, template[k]):
                    return False
            return True
        elif isinstance(value, list):
            if len(value) != len(template):
                return False
            for i in range(len(value)):
                if not cls.__eq__(value[i], template[i]):
                    return False
            return True
        else:
            return value == template


@pytest.mark.requires("ain")
def test_ainetwork_toolkit() -> None:
    def get(path, type="value", default=None):
        ref = ain.db.ref(path)
        value = asyncio.run(
            {
                "value": ref.getValue,
                "rule": ref.getRule,
                "owner": ref.getOwner,
            }[type]()
        )
        return default if value is None else value

    def validate(path, template, type="value"):
        value = get(path, type)
        return Match.__eq__(value, template)

    toolkit = AINetworkToolkit(network="testnet")
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    agent = initialize_agent(
        tools=toolkit.get_tools(),
        llm=llm,
        verbose=True,
        agent=AgentType.OPENAI_FUNCTIONS,
    )
    ain = toolkit.get_tools()[0].interface
    self_address = ain.wallet.defaultAccount.address
    co_address = "0x6813Eb9362372EEF6200f3b1dbC3f819671cBA69"

    # Test creating an app
    UUID = uuid.UUID(
        int=(int(time.time() * 1000) << 64) | (uuid.uuid4().int & ((1 << 64) - 1))
    )
    app_name = f"_langchain_test__{str(UUID).replace('-', '_')}"
    agent.run(f"""Create app {app_name}""")
    validate(f"/manage_app/{app_name}/config", {"admin": {self_address: True}})
    validate(f"/apps/{app_name}/DB", None, "owner")

    # Test reading owner config
    agent.run(f"""Read owner config of /apps/{app_name}/DB .""")
    assert ...

    # Test granting owner config
    agent.run(
        f"""Grant owner authority to {co_address} for edit write rule permission of /apps/{app_name}/DB_co ."""
    )
    validate(
        f"/apps/{app_name}/DB_co",
        {
            ".owner": {
                "owners": {
                    co_address: {
                        "branch_owner": False,
                        "write_function": False,
                        "write_owner": False,
                        "write_rule": True,
                    }
                }
            }
        },
        "owner",
    )

    # Test reading owner config
    agent.run(f"""Read owner config of /apps/{app_name}/DB_co .""")
    assert ...

    # Test reading owner config
    agent.run(f"""Read owner config of /apps/{app_name}/DB .""")
    assert ...  # Check if owner {self_address} exists

    # Test reading a value
    agent.run(f"""Read value in /apps/{app_name}/DB""")
    assert ...  # empty

    # Test writing a value
    agent.run(f"""Write value {{1: 1904, 2: 43}} in /apps/{app_name}/DB""")
    validate(f"/apps/{app_name}/DB", {1: 1904, 2: 43})

    # Test reading a value
    agent.run(f"""Read value in /apps/{app_name}/DB""")
    assert ...  # check value

    # Test reading a rule
    agent.run(f"""Read write rule of app {app_name} .""")
    assert ...  # check rule that self_address exists

    # Test sending AIN
    balance = get(f"/accounts/{co_address}/balance", default=0)
    if balance < 1:
        try:
            with urllib.request.urlopen(
                f"http://faucet.ainetwork.ai/api/test/{self_address}/"
            ) as response:
                try_test = response.getcode()
        except HTTPError as e:
            try_test = e.getcode()
    else:
        try_test = 200

    if try_test == 200:
        agent.run(f"""Send 1 AIN to {co_address}""")
        assert balance + 1 == get(f"/accounts/{co_address}/balance", default=0)
