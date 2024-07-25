// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/Galgobot.sol";
import "./mocks/MockERC20.sol";
import "./mocks/MockWETH.sol";
import "./mocks/MockUniswapV2Router.sol";
import "./mocks/MockBalancerVault.sol";

contract GalgobotTest is Test {
    Galgobot public galgobot;
    MockWETH public weth;
    MockERC20 public tokenA;
    MockERC20 public tokenB;
    MockUniswapV2Router public uniswapRouter;
    MockBalancerVault public balancerVault;

    address public owner = address(1);

    function setUp() public {
        weth = new MockWETH();
        tokenA = new MockERC20("Token A", "TKNA");
        tokenB = new MockERC20("Token B", "TKNB");
        uniswapRouter = new MockUniswapV2Router();
        balancerVault = new MockBalancerVault();

        galgobot = new Galgobot(owner, address(weth));

        // Fund the contract with some WETH
        weth.deposit{value: 10 ether}();
        weth.transfer(address(galgobot), 10 ether);
    }

    function testFlashLoanArbitrage() public {
        // Setup initial balances
        tokenA.mint(address(balancerVault), 1000 ether);
        tokenB.mint(address(uniswapRouter), 1000 ether);

        // Prepare flashloan data
        uint256 flashLoanAmount = 100 ether;
        address[] memory path = new address[](2);
        path[0] = address(tokenA);
        path[1] = address(tokenB);

        bytes memory flashLoanData = abi.encode(
            flashLoanAmount,
            address(uniswapRouter),
            address(tokenA),
            address(tokenB),
            address(balancerVault),
            path
        );

        // Perform the arbitrage
        vm.prank(owner);
        (bool success, ) = address(galgobot).call(flashLoanData);
        assertTrue(success, "Arbitrage execution failed");

        // Check if the arbitrage was profitable
        uint256 profit = weth.balanceOf(address(galgobot)) - 10 ether;
        assertGt(profit, 0, "Arbitrage was not profitable");
    }

    function testRecoverToken() public {
        tokenA.mint(address(galgobot), 100 ether);

        uint256 initialBalance = tokenA.balanceOf(owner);

        vm.prank(owner);
        galgobot.recoverToken(address(tokenA));

        uint256 finalBalance = tokenA.balanceOf(owner);
        assertEq(finalBalance - initialBalance, 100 ether - 1, "Token recovery failed");
    }

    function testApproveRouter() public {
        address[] memory tokens = new address[](2);
        tokens[0] = address(tokenA);
        tokens[1] = address(tokenB);

        galgobot.approveRouter(address(uniswapRouter), tokens, true);

        assertEq(tokenA.allowance(address(galgobot), address(uniswapRouter)), type(uint256).max, "Token A approval failed");
        assertEq(tokenB.allowance(address(galgobot), address(uniswapRouter)), type(uint256).max, "Token B approval failed");
    }
}