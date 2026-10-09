import asyncio
import json
import os
import aiofiles
import ssl
import ujson
import time
import logging
import functools
from typing import List, Any, Optional, Callable, Union, Tuple, Dict

from web3 import Web3
from web3.eth import Contract
from web3.contract import ContractFunction
from web3.types import (
    TxParams,
    Wei,
    Address,
    ChecksumAddress,
    ENS,
    Nonce,
    HexBytes,
)
from eth_utils import is_same_address
from eth_typing import AnyAddress

# TODO: 注所有的ETH在BSC是BNB，所有的WETH在BSC是WBNB
ETH_ADDRESS = "0x0000000000000000000000000000000000000000"

logger = logging.getLogger(__name__)


# TODO: Consider dropping support for ENS altogether and instead use AnyAddress
AddressLike = Union[Address, ChecksumAddress, ENS]


class InvalidToken(Exception):
    def __init__(self, address: Any) -> None:
        Exception.__init__(self, f"Invalid token address: {address}")


class InsufficientBalance(Exception):
    def __init__(self, had: int, needed: int) -> None:
        Exception.__init__(self, f"Insufficient balance. Had {had}, needed {needed}")


async def _load_abi(name: str) -> str:
    path = f"{os.path.dirname(os.path.abspath(__file__))}/assets/"

    async with aiofiles.open(path + f"{name}.abi", mode='r') as f:
        abi = await f.read()
    return json.loads(abi)


def check_approval(method: Callable) -> Callable:
    """Decorator to check if user is approved for a token. It approves them if they
        need to be approved."""

    @functools.wraps(method)
    def approved(self: Any, *args: Any, **kwargs: Any) -> Any:
        # Check to see if the first token is actually ETH
        token = args[0] if args[0] != ETH_ADDRESS else None
        token_two = None

        # Check second token, if needed
        if method.__name__ == "make_trade" or method.__name__ == "make_trade_output":
            token_two = args[1] if args[1] != ETH_ADDRESS else None

        # Approve both tokens, if needed
        approved_status = approved_status2 = True
        if token:
            is_approved = self._is_approved(token)
            if not is_approved:
                approved_status = self.approve(token)
        if token_two:
            is_approved = self._is_approved(token_two)
            if not is_approved:
                approved_status2 = self.approve(token_two)

        if approved_status and approved_status2:
            return method(self, *args, **kwargs)
        else:
            return False

    return approved


def supports(versions: List[int]) -> Callable:
    def g(f: Callable) -> Callable:
        @functools.wraps(f)
        def check_version(self: "MdexSwap", *args: List, **kwargs: Dict) -> Any:
            if self.version not in versions:
                raise Exception(
                    "Function does not support version of MdexSwap passed to constructor"
                )
            return f(self, *args, **kwargs)

        return check_version

    return g


def _str_to_addr(s: str) -> AddressLike:
    if s.startswith("0x"):
        return Address(bytes.fromhex(s[2:]))
    elif s.endswith(".eth"):
        return ENS(s)
    else:
        raise Exception(f"Couldn't convert string '{s}' to AddressLike")


def _addr_to_str(a: AddressLike) -> str:
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

    raise InvalidToken(a)


def _validate_address(a: AddressLike) -> None:
    assert _addr_to_str(a)


_netid_to_name = {1: "mainnet", 4: "rinkeby", 128: 'heco'}


class MdexSwap:
    def __init__(
        self,
        node_url,
        provider: str = None,
        web3: Web3 = None,

    ) -> None:


        if web3:
            self.w3 = web3
        else:
            # Initialize web3. Extra provider for testing.
            self.provider = provider if provider else \
                Web3.AsyncHTTPProvider(node_url, request_kwargs={
                    "timeout": 5, "ssl": ssl._create_unverified_context()
                })

            self.w3 = Web3(provider=self.provider)
        self.node_url_print = node_url

    @functools.lru_cache()
    async def erc20_contract(self, token_addr: AddressLike) -> Contract:
        return await self._load_contract(abi_name="bep20", address=token_addr)

    @functools.lru_cache()
    @supports([2])
    def get_weth_address(self) -> ChecksumAddress:
        # Contract calls should always return checksummed addresses
        address: ChecksumAddress = self.router.functions.WHT().call()
        return address

    async def _load_contract(self, abi_name: str, address: AddressLike) -> Contract:
        return self.w3.eth.contract(address=address, abi=await _load_abi(abi_name))

    # ------ Exchange ------------------------------------------------------------------
    @supports([1, 2])
    def get_fee_maker(self) -> float:
        """Get the maker fee."""
        return 0

    @supports([1, 2])
    def get_fee_taker(self) -> float:
        """Get the taker fee."""
        return 0.003

    # ------ Market --------------------------------------------------------------------
    @supports([1, 2])
    def get_eth_token_input_price(self, token: AddressLike, qty: Wei) -> Wei:
        """Public price for ETH to Token trades with an exact input."""
        price = self.router.functions.getAmountsOut(
            qty, [self.get_weth_address(), token]
        ).call()[-1]
        return price

    @supports([1, 2])
    def get_token_eth_input_price(self, token: AddressLike, qty: int) -> int:
        """Public price for token to ETH trades with an exact input."""
        price = self.router.functions.getAmountsOut(
            qty, [token, self.get_weth_address()]
        ).call()[-1]
        return price

    @supports([2])
    def get_token_token_input_price(
        self, token0: AnyAddress, token1: AnyAddress, qty: int
    ) -> int:
        """Public price for token to token trades with an exact input."""
        # If one of the tokens are WHT, delegate to appropriate call.
        # See: https://github.com/shanefontaine/uniswap-python/issues/22
        if is_same_address(token0, self.get_weth_address()):
            return int(self.get_eth_token_input_price(token1, qty))
        elif is_same_address(token1, self.get_weth_address()):
            return int(self.get_token_eth_input_price(token0, qty))

        price: int = self.router.functions.getAmountsOut(
            qty, [token0, self.get_weth_address(), token1]
        ).call()[-1]
        return price

    @supports([1, 2])
    def get_eth_token_output_price(self, token: AddressLike, qty: int) -> Wei:
        """Public price for ETH to Token trades with an exact output."""
        price = self.router.functions.getAmountsIn(
            qty, [self.get_weth_address(), token]
        ).call()[0]
        return price

    @supports([1, 2])
    def get_token_eth_output_price(self, token: AddressLike, qty: Wei) -> int:
        """Public price for token to ETH trades with an exact output."""
        price = self.router.functions.getAmountsIn(
            qty, [token, self.get_weth_address()]
        ).call()[0]
        return price

    @supports([2])
    def get_token_token_output_price(
        self, token0: AnyAddress, token1: AnyAddress, qty: int
    ) -> int:
        """Public price for token to token trades with an exact output."""
        # If one of the tokens are WHT, delegate to appropriate call.
        # See: https://github.com/shanefontaine/uniswap-python/issues/22
        # TODO: Will these equality checks always work? (Address vs ChecksumAddress vs str)
        if is_same_address(token0, self.get_weth_address()):
            return int(self.get_eth_token_output_price(token1, qty))
        elif is_same_address(token1, self.get_weth_address()):
            return int(self.get_token_eth_output_price(token0, qty))

        price: int = self.router.functions.getAmountsIn(
            qty, [token0, self.get_weth_address(), token1]
        ).call()[0]
        return price

    # ------ Wallet balance ------------------------------------------------------------
    def get_eth_balance(self) -> Wei:
        """Get the balance of ETH in a wallet."""
        return self.w3.eth.getBalance(self.address)

    def get_token_balance(self, token: AddressLike) -> int:
        """Get the balance of a token in a wallet."""
        _validate_address(token)
        if _addr_to_str(token) == ETH_ADDRESS:
            return self.get_eth_balance()
        erc20 = self.erc20_contract(token)
        balance: int = erc20.functions.balanceOf(self.address).call()
        return balance

    def get_one_token_balance(self, token: AddressLike, address: AddressLike):
        _validate_address(token)
        erc20 = self.erc20_contract(token)
        balance: int = erc20.functions.balanceOf(address).call()
        return balance

    # ------ Make Trade ----------------------------------------------------------------
    @check_approval
    def make_trade(
        self,
        input_token: AddressLike,
        output_token: AddressLike,
        qty: Union[int, Wei],
        recipient: AddressLike = None,
    ) -> HexBytes:
        """Make a trade by defining the qty of the input token."""
        if input_token == ETH_ADDRESS:
            return self._eth_to_token_swap_input(output_token, Wei(qty), recipient)
        else:
            balance = self.get_token_balance(input_token)
            if balance < qty:
                raise InsufficientBalance(balance, qty)
            if output_token == ETH_ADDRESS:
                return self._token_to_eth_swap_input(input_token, qty, recipient)
            else:
                return self._token_to_token_swap_input(
                    input_token, qty, output_token, recipient
                )

    @check_approval
    def make_trade_output(
        self,
        input_token: AddressLike,
        output_token: AddressLike,
        qty: Union[int, Wei],
        recipient: AddressLike = None,
    ) -> HexBytes:
        """Make a trade by defining the qty of the output token."""
        if input_token == ETH_ADDRESS:
            balance = self.get_eth_balance()
            need = self.get_eth_token_output_price(output_token, qty)
            if balance < need:
                raise InsufficientBalance(balance, need)
            return self._eth_to_token_swap_output(output_token, qty, recipient)
        elif output_token == ETH_ADDRESS:
            qty = Wei(qty)
            return self._token_to_eth_swap_output(input_token, qty, recipient)
        else:
            return self._token_to_token_swap_output(
                input_token, qty, output_token, recipient
            )

    def _eth_to_token_swap_input(
        self, output_token: AddressLike, qty: Wei, recipient: Optional[AddressLike]
    ) -> HexBytes:
        """Convert ETH to tokens given an input amount."""
        eth_balance = self.get_eth_balance()
        if qty > eth_balance:
            raise InsufficientBalance(eth_balance, qty)

        if recipient is None:
            recipient = self.address
        amount_out_min = int(
            (1 - self.max_slippage)
            * self.get_eth_token_input_price(output_token, qty)
        )
        return self._build_and_send_tx(
            self.router.functions.swapExactETHForTokens(
                amount_out_min,
                [self.get_weth_address(), output_token],
                recipient,
                self._deadline(),
            ),
            self._get_tx_params(qty),
        )

    def _token_to_eth_swap_input(
        self, input_token: AddressLike, qty: int, recipient: Optional[AddressLike]
    ) -> HexBytes:
        """Convert tokens to ETH given an input amount."""
        # Balance check
        input_balance = self.get_token_balance(input_token)
        if qty > input_balance:
            raise InsufficientBalance(input_balance, qty)

        if recipient is None:
            recipient = self.address
        amount_out_min = int(
            (1 - self.max_slippage)
            * self.get_token_eth_input_price(input_token, qty)
        )
        return self._build_and_send_tx(
            self.router.functions.swapExactTokensForETH(
                qty,
                amount_out_min,
                [input_token, self.get_weth_address()],
                recipient,
                self._deadline(),
            ),
        )

    def _token_to_token_swap_input(
        self,
        input_token: AddressLike,
        qty: int,
        output_token: AddressLike,
        recipient: Optional[AddressLike],
    ) -> HexBytes:
        """Convert tokens to tokens given an input amount."""
        if recipient is None:
            recipient = self.address
        min_tokens_bought = int(
            (1 - self.max_slippage)
            * self.get_token_token_input_price(input_token, output_token, qty)
        )
        return self._build_and_send_tx(
            self.router.functions.swapExactTokensForTokens(
                qty,
                min_tokens_bought,
                [input_token, self.get_weth_address(), output_token],
                recipient,
                self._deadline(),
            ),
        )

    def _eth_to_token_swap_output(
        self, output_token: AddressLike, qty: int, recipient: Optional[AddressLike]
    ) -> HexBytes:
        """Convert ETH to tokens given an output amount."""
        if recipient is None:
            recipient = self.address
        eth_qty = self.get_eth_token_output_price(output_token, qty)
        return self._build_and_send_tx(
            self.router.functions.swapETHForExactTokens(
                qty,
                [self.get_weth_address(), output_token],
                recipient,
                self._deadline(),
            ),
            self._get_tx_params(eth_qty),
        )

    def _token_to_eth_swap_output(
        self, input_token: AddressLike, qty: Wei, recipient: Optional[AddressLike]
    ) -> HexBytes:
        """Convert tokens to ETH given an output amount."""
        # Balance check
        input_balance = self.get_token_balance(input_token)
        cost = self.get_token_eth_output_price(input_token, qty)
        if cost > input_balance:
            raise InsufficientBalance(input_balance, cost)

        max_tokens = int((1 + self.max_slippage) * cost)
        return self._build_and_send_tx(
            self.router.functions.swapTokensForExactETH(
                qty,
                max_tokens,
                [input_token, self.get_weth_address()],
                self.address,
                self._deadline(),
            ),
        )

    def _token_to_token_swap_output(
        self,
        input_token: AddressLike,
        qty: int,
        output_token: AddressLike,
        recipient: Optional[AddressLike],
    ) -> HexBytes:
        """Convert tokens to tokens given an output amount."""
        cost = self.get_token_token_output_price(input_token, output_token, qty)
        amount_in_max = int((1 + self.max_slippage) * cost)
        return self._build_and_send_tx(
            self.router.functions.swapTokensForExactTokens(
                qty,
                amount_in_max,
                [input_token, self.get_weth_address(), output_token],
                self.address,
                self._deadline(),
            ),
        )

    # ------ Approval Utils ------------------------------------------------------------
    def approve(self, token: AddressLike, max_approval: Optional[int] = None):
        """Give an exchange/router max approval of a token."""
        max_approval = self.max_approval_int if not max_approval else max_approval
        contract_addr = self.router_address
        function = self.erc20_contract(token).functions.approve(
            contract_addr, max_approval
        )
        logger.info(f"Approving {_addr_to_str(token)}...")
        tx = self._build_and_send_tx(function)

        # 设置2min的超时时间
        try:
            self.w3.eth.waitForTransactionReceipt(tx, timeout=120)
        except:
            return False
        else:
            # Add extra sleep to let tx propogate correctly
            time.sleep(1)
            return True

    def _is_approved(self, token: AddressLike) -> bool:
        """Check to see if the exchange and token is approved."""
        _validate_address(token)
        contract_addr = self.router_address
        amount = (
            self.erc20_contract(token)
            .functions.allowance(self.address, contract_addr)
            .call()
        )
        if amount / 1e18 > 10000000:
            return True
        else:
            return False

    # ------ Tx Utils ------------------------------------------------------------------
    def _deadline(self) -> int:
        """Get a predefined deadline. 10min by default (same as the MdexSwap SDK)."""
        return int(time.time()) + 10 * 60

    def _build_and_send_tx(
        self, function: ContractFunction, tx_params: Optional[TxParams] = None
    ) -> HexBytes:
        """Build and send a transaction."""
        if not tx_params:
            tx_params = self._get_tx_params()
        transaction = function.buildTransaction(tx_params)
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.private_key
        )
        # TODO: This needs to get more complicated if we want to support replacing a transaction
        # FIXME: This does not play nice if transactions are sent from other places using the same wallet.
        try:
            return self.w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        finally:
            logger.debug(f"nonce: {tx_params['nonce']}")
            self.last_nonce = Nonce(tx_params["nonce"] + 1)

    def _get_tx_params(self, value: Wei = Wei(0), gas: Wei = Wei(250000)) -> TxParams:
        """Get generic transaction parameters."""
        return {
            "from": _addr_to_str(self.address),
            "value": value,
            "gas": gas,
            "nonce": max(
                self.last_nonce, self.w3.eth.getTransactionCount(self.address)
            ),
        }

async def test():
    use_note = MdexSwap(node_url="http://172.29.205.4:31000")
    first_address = '0xf1f955016EcbCd7321c7266BccFB96c68ea5E49b' # RLY
    second_address = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2' # WETH

    pair_address = '0x27fD0857F0EF224097001E87e61026E39e1B04d1'
    heco_first = await use_note.erc20_contract(Web3.to_checksum_address(first_address))
    heco_second = await use_note.erc20_contract(Web3.to_checksum_address(second_address))
    t1 = asyncio.create_task(heco_first.functions.balanceOf(Web3.to_checksum_address(pair_address)).call())
    t2 = asyncio.create_task(heco_second.functions.balanceOf(Web3.to_checksum_address(pair_address)).call())

    b1 = await t1
    b2 = await t2
    print(b2 / b1)

