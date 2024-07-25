// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "openzeppelin-contracts/token/ERC20/IERC20.sol";
import "../src/interface/IBalancer.sol";

contract MockBalancerVault is IBalancerVault {
    function flashLoan(
        IFlashLoanRecipient recipient,
        IERC20[] memory tokens,
        uint256[] memory amounts,
        bytes memory userData
    ) external {
        for (uint256 i = 0; i < tokens.length; i++) {
            IERC20(tokens[i]).transfer(address(recipient), amounts[i]);
        }

        recipient.receiveFlashLoan(tokens, amounts, new uint256[](tokens.length), userData);

        for (uint256 i = 0; i < tokens.length; i++) {
            IERC20(tokens[i]).transferFrom(address(recipient), address(this), amounts[i]);
        }
    }
}