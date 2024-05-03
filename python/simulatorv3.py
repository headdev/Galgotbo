class UniswapV3Simulator:
    def __init__(self):
        self.Q96 = 2**96
        self.MAX_TICK = 887272
        self.MIN_TICK = -887272

    def get_sqrt_ratio_at_tick(self, tick: int) -> int:
        """
        Calculates sqrt(1.0001^tick) * 2^96
        """
        abs_tick = abs(tick)
        ratio = 0xfffcb933bd6fad37aa2d162d1a594001 if abs_tick & 0x1 != 0 else 0x100000000000000000000000000000000
        if abs_tick & 0x2 != 0:
            ratio = (ratio * 0xfff97272373d413259a46990580e213a) >> 128
        if abs_tick & 0x4 != 0:
            ratio = (ratio * 0xfff2e50f5f656932ef12357cf3c7fdcc) >> 128
        if abs_tick & 0x8 != 0:
            ratio = (ratio * 0xffe5caca7e10e4e61c3624eaa0941cd0) >> 128
        if abs_tick & 0x10 != 0:
            ratio = (ratio * 0xffcb9843d60f6159c9db58835c926644) >> 128
        if abs_tick & 0x20 != 0:
            ratio = (ratio * 0xff973b41fa98c081472e6896dfb254c0) >> 128
        if abs_tick & 0x40 != 0:
            ratio = (ratio * 0xff2ea16466c96a3843ec78b326b52861) >> 128
        if abs_tick & 0x80 != 0:
            ratio = (ratio * 0xfe5dee046a99a2a811c461f1969c3053) >> 128
        if abs_tick & 0x100 != 0:
            ratio = (ratio * 0xfcbe86c7900a88aedcffc83b479aa3a4) >> 128
        if abs_tick & 0x200 != 0:
            ratio = (ratio * 0xf987a7253ac413176f2b074cf7815e54) >> 128
        if abs_tick & 0x400 != 0:
            ratio = (ratio * 0xf3392b0822b70005940c7a398e4b70f3) >> 128
        if abs_tick & 0x800 != 0:
            ratio = (ratio * 0xe7159475a2c29b7443b29c7fa6e889d9) >> 128
        if abs_tick & 0x1000 != 0:
            ratio = (ratio * 0xd097f3bdfd2022b8845ad8f792aa5825) >> 128
        if abs_tick & 0x2000 != 0:
            ratio = (ratio * 0xa9f746462d870fdf8a65dc1f90e061e5) >> 128
        if abs_tick & 0x4000 != 0:
            ratio = (ratio * 0x70d869a156d2a1b890bb3df62baf32f7) >> 128
        if abs_tick & 0x8000 != 0:
            ratio = (ratio * 0x31be135f97d08fd981231505542fcfa6) >> 128
        if abs_tick & 0x10000 != 0:
            ratio = (ratio * 0x9aa508b5b7a84e1c677de54f3e99bc9) >> 128
        if abs_tick & 0x20000 != 0:
            ratio = (ratio * 0x5d6af8dedb81196699c329225ee604) >> 128
        if abs_tick & 0x40000 != 0:
            ratio = (ratio * 0x2216e584f5fa1ea926041bedfe98) >> 128
        if abs_tick & 0x80000 != 0:
            ratio = (ratio * 0x48a170391f7dc42444e8fa2) >> 128

        if tick > 0:
            ratio = self.Q96 ** 2 // ratio

        return ratio

    def sqrtx96_to_price(self,
                         sqrtx96: int,
                         decimal_in: int,
                         decimal_out: int,
                         token0_in: bool) -> float:
        """
        Gets the price_out using the sqrt_ratioX96
        """
        sqrt_pq_x96 = sqrtx96
        sqrt_pq_xq = self.Q96 * self.Q96 * (10 ** decimal_out) // sqrt_pq_x96 // sqrt_pq_x96 // (10 ** decimal_in)

        if token0_in:
            price = 1 / (sqrt_pq_xq / self.Q96)
        else:
            price = sqrt_pq_xq / self.Q96
        return price

    def get_amount_out(self,
                       amount_in: float,
                       sqrt_ratio_current_x96: int,
                       sqrt_ratio_target_x96: int,
                       liquidity: int,
                       fee: int) -> int:
        fee_pct = fee / 1000000
        numerator = liquidity * (sqrt_ratio_current_x96 - sqrt_ratio_target_x96)
        denominator = sqrt_ratio_current_x96 * sqrt_ratio_target_x96
        amount_out = numerator // denominator
        fee_amount = int(amount_in * fee_pct)
        return int(amount_out - fee_amount)

    def get_amount_in(self,
                      amount_out: float,
                      sqrt_ratio_current_x96: int,
                      sqrt_ratio_target_x96: int,
                      liquidity: int,
                      fee: int) -> int:
        fee_pct = fee / 1000000
        numerator = liquidity * (sqrt_ratio_current_x96 - sqrt_ratio_target_x96)
        denominator = sqrt_ratio_current_x96 * sqrt_ratio_target_x96
        amount_in = numerator // denominator
        fee_amount = int(amount_in * fee_pct)
        return int(amount_in + fee_amount)

    def get_max_amount_in(self,
                          sqrt_ratio_current_x96: int,
                          sqrt_ratio_target_x96: int,
                          liquidity: int,
                          fee: int,
                          token0_in: bool,
                          max_amount_in: float,
                          step_size: float,
                          slippage_tolerance_lower: float,
                          slippage_tolerance_upper: float) -> float:
        """
        Calculates the maximum amount_in we can swap to get amount_out
        This method accounts for both: 1. fee, 2. price impact
        Also, we calculate the price quote using sqrt_ratioX96 and use that price
        to account for slippage tolerance
        We make sure that:

        amount_out >= price_quote * (1 - slippage_tolerance)

        This method uses binary search to find the optimized amount_in value
        To reduce the search space, we pre-set values such as: max_amount_in, step_size,
                                                               slippage_tolerance_lower/upper

        * Slippage tips:

        1. Setting slippage_tolerance_lower: 0, slippage_tolerance_upper: 0.001
        will find the amount_in with a slippage below 0.1% --> this method is faster

        2. However, if you want to fine tune your amount_in, you should set the tolerance level like:
        slippage_tolerance_lower: 0.0009, slippage_tolerance_upper: 0.001

        :param max_amount_in: the max_amount_in used in binary search
        :param step_size: the order step_size. ex) 0.01, 0.1, 1, 10, etc...
        :param slippage_tolerance_lower: 0.01 (1%), 0.005 (0.5%), ...
        :param slippage_tolerance_upper: 0.01 (1%), ...
        """
        fee_pct = fee / 1000000
        price_quote = self.sqrtx96_to_price(sqrt_ratio_current_x96,
                                            0,
                                            0,
                                            token0_in)
        price_quote = price_quote * (1 - fee_pct)

        optimized_in = 0

        left = 0
        right = max_amount_in

        max_amount_out = self.get_amount_out(right,
                                             sqrt_ratio_current_x96,
                                             sqrt_ratio_target_x96,
                                             liquidity,
                                             fee)
        amount_out_rate = max_amount_out / right
        slippage = (price_quote - amount_out_rate) / price_quote

        if slippage < slippage_tolerance_lower:
            """
            If the maximum amount_in value is within the slippage tolerance level,
            we simply return that value
            """
            optimized_in = right
        else:
            while left <= right:
                mid = ((left + right) / 2) // step_size / (1 / step_size)
                amount_out = self.get_amount_out(mid,
                                                 sqrt_ratio_current_x96,
                                                 sqrt_ratio_target_x96,
                                                 liquidity,
                                                 fee)
                amount_out_rate = amount_out / mid
                slippage = (price_quote - amount_out_rate) / price_quote
                if slippage_tolerance_lower <= slippage <= slippage_tolerance_upper:
                    optimized_in = mid
                    break
                else:
                    if slippage < slippage_tolerance_lower:
                        left = mid
                    else:
                        right = mid

        return optimized_in


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from web3 import Web3
    import requests
    from poolsv3 import load_all_pools_from_v3
    from paths import generate_triangular_paths, simulate_v3_path

    from constants import logger
    from multi import batch_get_uniswap_v3_slot0

    load_dotenv(override=True)

    response = requests.get('https://lively-restless-pond.matic.quiknode.pro/2b6686dcae197a1385f8497ae93d3cfaa79b5d04',  verify=False)
    HTTPS_URL = os.getenv('HTTPS_URL')

    # Example on Ethereum
    factory_addresses = [
        '0x1F98431c8aD98523631AE4a59f267346ea31F984',
    ]
    factory_blocks = [
        55859483,
    ]

    pools = load_all_pools_from_v3(HTTPS_URL, factory_addresses, factory_blocks, 1000)

    weth_address = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
    paths = generate_triangular_paths(pools, weth_address)

    # Filter pools that were used in arb paths
    pools = {}
    for path in paths:
        pools[path.pool_1.address] = path.pool_1
        pools[path.pool_2.address] = path.pool_2
        pools[path.pool_3.address] = path.pool_3

    sqrtPriceX96 = batch_get_uniswap_v3_slot0(HTTPS_URL, pools)

    # Do the below if you know the real amount_in
    path = paths[0]
    amount_out = simulate_v3_path(path, 1000000, sqrtPriceX96)
    print(path, amount_out)

    amount_out = path.simulate_v3_path(1, sqrtPriceX96)
    print(amount_out)

    # optimizing amount_in
    max_amount_in = 10000
    step_size = 100
    amount_ins = list(range(max_amount_in // step_size))
    amount_outs = [path.simulate_v3_path(int(step_size * i), sqrtPriceX96) for i in amount_ins]
    print(amount_outs)
