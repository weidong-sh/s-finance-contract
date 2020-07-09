import itertools

import pytest

from tests.conftest import PRECISIONS

INITIAL_AMOUNTS = [10**(i+6) for i in PRECISIONS]


@pytest.fixture(scope="module", autouse=True)
def setup(alice, bob, aave_coins, underlying_coins, swap):
    for coin, amount in zip(aave_coins, INITIAL_AMOUNTS):
        coin._mint_for_testing(alice, amount, {'from': alice})
        coin.approve(swap, 2**256-1, {'from': alice})

    for coin in underlying_coins:
        coin.approve(swap, 2**256-1, {'from': bob})

    swap.add_liquidity(INITIAL_AMOUNTS, 0, {'from': alice})


@pytest.mark.parametrize("sending,receiving,other", itertools.permutations([0, 1, 2], 3))
@pytest.mark.parametrize(
    "fee,admin_fee", itertools.combinations_with_replacement([0, 0.04, 0.1337, 0.5], 2)
)
def test_exchange_underlying(rpc, alice, bob, swap, underlying_coins, sending, receiving, other, fee, admin_fee):
    if fee or admin_fee:
        swap.commit_new_fee(int(10**10 * fee), int(10**10 * admin_fee), 0, {'from': alice})
        rpc.sleep(86400*3)
        swap.apply_new_fee({'from': alice})

    amount = 10**PRECISIONS[sending]
    underlying_coins[sending]._mint_for_testing(bob, amount, {'from': bob})
    swap.exchange_underlying(sending, receiving, amount, 0, {'from': bob})

    assert underlying_coins[sending].balanceOf(bob) == 0
    assert underlying_coins[other].balanceOf(bob) == 0

    received = underlying_coins[receiving].balanceOf(bob)
    assert 0.9999-fee < received / 10**PRECISIONS[receiving] < 1-fee

    expected_admin_fee = 10**PRECISIONS[receiving] * fee * admin_fee
    if expected_admin_fee:
        assert (expected_admin_fee * 0.999) <= swap.admin_balances(receiving) <= expected_admin_fee
    else:
        assert swap.admin_balances(receiving) == 0


@pytest.mark.parametrize("sending,receiving", itertools.permutations([0, 1, 2], 2))
def test_underlying_min_dy(bob, swap, underlying_coins, sending, receiving):
    amount = 10**PRECISIONS[sending]

    underlying_coins[sending]._mint_for_testing(bob, amount, {'from': bob})

    min_dy = swap.get_dy(sending, receiving, amount)
    swap.exchange_underlying(sending, receiving, amount, min_dy, {'from': bob})

    assert underlying_coins[receiving].balanceOf(bob) == min_dy