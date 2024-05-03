import math
import multiprocessing
from web3 import Web3
from typing import Dict
from multicall import Call, Multicall
from poolsv3 import Poolv3
from constants import logger
from web3.middleware import geth_poa_middleware
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import requests

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_uniswap_v3_slot0(https_url: str, pools: Dict[str, Poolv3]):
    w3 = Web3(Web3.HTTPProvider(https_url, request_kwargs={'verify': False}))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    signature = 'slot0()((uint160,int24,uint16,uint16,uint16,uint8,bool))' # sqrtPriceX96, tick, observationIndex, observationCardinality, observationCardinalityNext, feeProtocol, unlocked

    calls = []
    for pool_address in pools:
        call = Call(
            pool_address,
            signature,
            [(pool_address, lambda x: x)]
        )
        calls.append(call)

    multicall = Multicall(calls, _w3=w3)
    result = multicall()

    slot0 = {k: v[0] for k, v in result.items()}

    """
    slot0:
    {
        '0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8': (1526350623543413024640558359979021026715832147638, 256819, 0, 1, 1, 0, True),
        '0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640': (1523585533016435498691267815985649526319479687826, 256232, 0, 1, 1, 0, True)
    }
    """

    return slot0

def batch_get_uniswap_v3_slot0(https_url: str, pools: Dict[str, Poolv3]):
    mp = multiprocessing.Pool()
    pools_cnt = len(pools)
    batch = max(1, math.ceil(pools_cnt / 250))  # Ensure batch is at least 1
    pools_per_batch = math.ceil(pools_cnt / batch)

    args = []
    for i in range(batch):
        start_idx = i * pools_per_batch
        end_idx = min(start_idx + pools_per_batch, pools_cnt)
        args.append((https_url, dict(list(pools.items())[start_idx:end_idx])))

    results = mp.starmap(get_uniswap_v3_slot0, args)

    slot0 = {}
    for result in results:
        slot0 = {**slot0, **result}

    return slot0

if __name__ == '__main__':
    import os
    import time
    from dotenv import load_dotenv
    from poolsv3 import load_all_pools_from_v3
    from pathsv3 import generate_triangular_paths

    load_dotenv(override=True)
    HTTPS_URL = os.getenv('HTTPS_URL')

    # Example on Ethereum
    factory_addresses = ['0x1F98431c8aD98523631AE4a59f267346ea31F984']
    factory_blocks = [55859483]

    pools = load_all_pools_from_v3(HTTPS_URL, factory_addresses, factory_blocks, 1000)
    logger.info(f'Pool count: {len(pools)}')

    weth_address = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
    paths = generate_triangular_paths(pools, weth_address)

    # Filter pools that were used in arb paths
    pools = {}
    for path in paths:
        pools[path.pool_1.address] = path.pool_1
        pools[path.pool_2.address] = path.pool_2
        pools[path.pool_3.address] = path.pool_3

    logger.info(f'New pool count: {len(pools)}')

    s = time.time()
    slot0 = batch_get_uniswap_v3_slot0(HTTPS_URL, pools)
    e = time.time()
    logger.info(f'Took: {e - s} seconds')
    logger.info(len(slot0))
    logger.info(slot0)
