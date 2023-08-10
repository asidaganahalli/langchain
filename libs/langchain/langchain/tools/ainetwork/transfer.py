import json
from typing import Optional, Type

from pydantic import BaseModel, Field

from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain.tools.ainetwork.base import AINBaseTool


class TransferSchema(BaseModel):
    transferAddress: str = Field(..., description="Address to transfer AIN to")
    amount: int = Field(..., description="Amount of AIN to transfer")


class AINTransfer(AINBaseTool):
    name: str = "AINtransfer"
    description: str = "Transfers AIN to a specified address"
    args_schema: Type[TransferSchema] = TransferSchema

    async def _arun(
        self,
        transferAddress: str,
        amount: int,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        try:
            res = await self.interface.wallet.transfer(
                transferAddress, amount, nonce=-1
            )
            return json.dumps(res, ensure_ascii=False)
        except Exception as e:
            return f"{type(e).__name__}: {str(e)}"
