import asyncio
import json
import ssl

import aiofiles
import ujson
import os

from eth_typing import Address
from web3 import Web3

ETH_ADDRESS = Web3.to_checksum_address('0x0000000000000000000000000000000000000000')

class Uniswap:
    def __init__(
        self,
        provider: str = None,
    ) -> None:
        self.provider = provider
        self.w3 = Web3(
            Web3.AsyncHTTPProvider(provider, request_kwargs={
                "timeout": 60, "ssl": ssl._create_unverified_context()
            })
        )
        self.quoter_task = asyncio.create_task(self._load_contract(
            abi_name="/quoter", address=_str_to_addr("0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"),
        ))
        self.quoter = None

    async def _load_contract(self, abi_name: str, address):
        return self.w3.eth.contract(address=address, abi=await _load_abi(abi_name))

    async def get_exacted_output_single(self, token_in, token_out, amountOut, fee):
        weth_address = Web3.to_checksum_address('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
        if self.quoter is None:
            self.quoter = await self.quoter_task
        qty = await self.quoter.functions.quoteExactOutputSingle(
            weth_address if token_in == ETH_ADDRESS else _str_to_addr(token_in),
            weth_address if token_out == ETH_ADDRESS else _str_to_addr(token_out),
            fee,
            amountOut,
            0
        ).call()
        return qty

    async def get_exacted_input_single(self, token_in, token_out, amountIn, fee):
        weth_address = Web3.to_checksum_address('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
        if self.quoter is None:
            self.quoter = await self.quoter_task
        qty = await self.quoter.functions.quoteExactInputSingle(
            weth_address if token_in == ETH_ADDRESS else _str_to_addr(token_in),
            weth_address if token_out == ETH_ADDRESS else _str_to_addr(token_out),
            fee,
            amountIn,
            0
        ).call()
        return qty


def _str_to_addr(s: str):
    if s.startswith("0x"):
        return Address(bytes.fromhex(s[2:]))
    else:
        raise Exception(f"Couldn't convert string '{s}' to AddressLike")

def _addr_to_str(a) -> str:
    if isinstance(a, bytes):
        # Address or ChecksumAddress
        addr: str = Web3.to_checksum_address("0x" + bytes(a).hex())
        return addr
    elif isinstance(a, str):
        if a.endswith(".eth"):
            # Address is ENS
            raise Exception("ENS not supported for this operation")
        elif a.startswith("0x"):
            addr = Web3.to_checksum_address(a)
            return addr

    raise ValueError('invalid token!!!')


async def _load_abi(name: str) -> str:
    path = f"{os.path.dirname(os.path.abspath(__file__))}"

    async with aiofiles.open(path + f"{name}.abi", mode='r') as f:
        abi = await f.read()
    return json.loads(abi)


async def test():
    uni_wrapper = Uniswap("http://172.29.205.4:31000")
    eth = '0x0000000000000000000000000000000000000000'
    currency = '0x6123B0049F904d730dB3C36a31167D9d4121fA6B'
    pool = '0x94981F69F7483AF3ae218CbfE65233cC3c60d93a'
    fee = 10000
    t2 = asyncio.create_task(uni_wrapper.get_exacted_input_single(eth, currency, int(1 * 1e18), int(fee)))
    data2 = await t2
    print(data2)

