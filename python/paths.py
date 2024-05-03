from tqdm import tqdm
from typing import Dict, List, Optional
import requests
from poolsv3 import Poolv3
from bundler import Path
from constants import logger
from simulatorv3 import UniswapV3Simulator
response = requests.get('https://lively-restless-pond.matic.quiknode.pro/2b6686dcae197a1385f8497ae93d3cfaa79b5d04',  verify=False)


class ArbPath:

    def __init__(self,
                 pool_1: Poolv3,
                 pool_2: Poolv3,
                 pool_3: Optional[Poolv3],
                 token_in_1: str,
                 token_out_1: str,
                 token_in_2: str,
                 token_out_2: str,
                 token_in_3: str,
                 token_out_3: str,
                 fee_1: int,
                 fee_2: int,
                 fee_3: int):

        self.pool_1 = pool_1
        self.pool_2 = pool_2
        self.pool_3 = pool_3
        self.token_in_1 = token_in_1
        self.token_out_1 = token_out_1
        self.token_in_2 = token_in_2
        self.token_out_2 = token_out_2
        self.token_in_3 = token_in_3
        self.token_out_3 = token_out_3
        self.fee_1 = fee_1
        self.fee_2 = fee_2
        self.fee_3 = fee_3

    @property
    def nhop(self) -> int:
        return 2 if self.pool_3 is None else 3

    def has_pool(self, pool: str) -> bool:
        is_pool_1 = self.pool_1.address == pool
        is_pool_2 = self.pool_2.address == pool
        is_pool_3 = self.pool_3.address == pool
        return is_pool_1 or is_pool_2 or is_pool_3

    def should_blacklist(self, blacklist_tokens: List[str]) -> bool:
        for i in range(self.nhop):
            token_in = getattr(self, f'token_in_{i + 1}')
            token_out = getattr(self, f'token_out_{i + 1}')
            if token_in in blacklist_tokens or token_out in blacklist_tokens:
                return True
        return False

    def simulate_v3_path(self, amount_in: int, sqrtPriceX96: Dict[str, int]) -> int:
        """
        Simulates the swap path for Uniswap V3 pools
        """
        token_in_decimals = self.pool_1.decimals0 if self.token_in_1 == self.pool_1.token0 else self.pool_1.decimals1
        real_amount_in = int(amount_in * (10 ** token_in_decimals))
        return simulate_v3_path(self, real_amount_in, sqrtPriceX96)

    def optimize_amount_in(self,
                           max_amount_in: int,
                           step_size: int,
                           sqrtPriceX96: Dict[str, int]) -> (int, int):
        # a simple brute force profit optimization
        token_in_decimals = self.pool_1.decimals0 if self.token_in_1 == self.pool_1.token0 else self.pool_1.decimals1
        optimized_in = 0
        profit = 0
        for amount_in in range(0, max_amount_in, step_size):
            amount_out = self.simulate_v3_path(amount_in, sqrtPriceX96)
            this_profit = amount_out - (amount_in * (10 ** token_in_decimals))
            if this_profit >= profit:
                optimized_in = amount_in
                profit = this_profit
            else:
                break
        return optimized_in, profit / (10 ** token_in_decimals)

    def to_path_params(self, routers: List[str]) -> List[Path]:
        path_params = []
        for i in range(self.nhop):
            pool = getattr(self, f'pool_{i + 1}')
            token_in = getattr(self, f'token_in_{i + 1}')
            token_out = getattr(self, f'token_out_{i + 1}')
            fee = getattr(self, f'fee_{i + 1}')
            path = Path(routers[i], token_in, token_out)
            path.fee = fee
            path_params.append(path)
        return path_params


def simulate_v3_path(path: ArbPath, amount_in: int, sqrtPriceX96: Dict[str, int]) -> int:
    sim = UniswapV3Simulator()

    for i in range(path.nhop):
        pool = getattr(path, f'pool_{i + 1}')
        token_in = getattr(path, f'token_in_{i + 1}')
        token_out = getattr(path, f'token_out_{i + 1}')
        fee = getattr(path, f'fee_{i + 1}')
        sqrt_ratio_current_x96 = sqrtPriceX96[pool.address]
        sqrt_ratio_target_x96 = sim.sqrtx96_to_price(sqrt_ratio_current_x96,
                                                     pool.decimals0,
                                                     pool.decimals1,
                                                     token_in == pool.token0)
        liquidity = pool.liquidity
        amount_out = sim.get_amount_out(amount_in, sqrt_ratio_current_x96, sqrt_ratio_target_x96, liquidity, fee)
        amount_in = amount_out

    return amount_out


def generate_triangular_paths(pools: Dict[str, Poolv3], token_in: str) -> List[ArbPath]:
    """
    A straightforward triangular arbitrage path finder for Uniswap V3.
    This call will find both 2-hop paths, 3-hop paths, but not more.
    Also, we define triangular arb. paths as a 3-hop swap path starting
    with token_in and ending with token_in:

    token_in --> token1 --> token2 --> token_in

    NOTE: this function is highly recursive, and can easily extend to n-hop paths.
    Refer to https://github.com/solidquant/whack-a-mole/blob/main/data/dex.py
    __generate_paths function for this.
    """
    paths = []

    pools = list(pools.values())

    for pool_1 in tqdm(pools,
                       total=len(pools),
                       ncols=100,
                       desc=f'Generating paths',
                       ascii=' =',
                       leave=True):
        pools_in_path = set()
        pools_in_path.add(pool_1.address)
        can_trade_1 = (pool_1.token0 == token_in) or (pool_1.token1 == token_in)
        if can_trade_1:
            token_in_1, token_out_1 = (pool_1.token0, pool_1.token1) if pool_1.token0 == token_in else (pool_1.token1, pool_1.token0)
            fee_1 = pool_1.fee
            if token_in_1 != token_in:
                continue

            for j in range(len(pools)):
                pool_2 = pools[j]
                pools_in_path.add(pool_2.address)
                can_trade_2 = (pool_2.token0 == token_out_1) or (pool_2.token1 == token_out_1)
                if can_trade_2:
                    token_in_2, token_out_2 = (pool_2.token0, pool_2.token1) if pool_2.token0 == token_out_1 else (pool_2.token1, pool_2.token0)
                    fee_2 = pool_2.fee
                    if token_out_1 != token_in_2:
                        continue

                    for k in range(len(pools)):
                        pool_3 = pools[k]
                        pools_in_path.add(pool_3.address)
                        can_trade_3 = (pool_3.token0 == token_out_2) or (pool_3.token1 == token_out_2)
                        if can_trade_3:
                            token_in_3, token_out_3 = (pool_3.token0, pool_3.token1) if pool_3.token0 == token_out_2 else (pool_3.token1, pool_3.token0)
                            fee_3 = pool_3.fee
                            if token_out_2 != token_in_3:
                                continue

                            if token_out_3 == token_in:
                                unique_pool_cnt = len(pools_in_path)

                                if unique_pool_cnt < 3:
                                    continue

                                arb_path = ArbPath(pool_1=pool_1,
                                                   pool_2=pool_2,
                                                   pool_3=pool_3,
                                                   token_in_1=token_in_1,
                                                   token_out_1=token_out_1,
                                                   token_in_2=token_in_2,
                                                   token_out_2=token_out_2,
                                                   token_in_3=token_in_3,
                                                   token_out_3=token_out_3,
                                                   fee_1=fee_1,
                                                   fee_2=fee_2,
                                                   fee_3=fee_3)
                                paths.append(arb_path)

    logger.info(f'Generated {len(paths)} 3-hop arbitrage paths')
    return paths


if __name__ == '__main__':
    from constants import HTTPS_URL
    from poolsv3 import load_all_pools_from_v3

    factory_addresses = [
        '0x1F98431c8aD98523631AE4a59f267346ea31F984',  # Uniswap V3
    ]
    factory_blocks = [
        55859483,
    ]

    pools = load_all_pools_from_v3(HTTPS_URL,
                                   factory_addresses,
                                   factory_blocks,
                                   50000)

    token_in = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'  # WETH
    paths = generate_triangular_paths(pools, token_in)
    # logger.info(paths)
