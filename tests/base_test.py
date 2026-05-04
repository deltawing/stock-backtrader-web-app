import unittest
from typing import Any, Dict, Optional, Type

import akshare as ak
import backtrader as bt
import pandas as pd

from strategy.base import BaseStrategy
from utils.backtest import setup_cerebro, _extract_results
from utils.load import load_strategy
from utils.schemas import BacktraderParams


class StrategyTest(unittest.TestCase):
    """策略测试基类"""

    def setUp(self):
        """测试前准备工作，加载数据和设置回测环境"""

        # 加载股票历史数据
        stock_hfq_df = ak.stock_zh_a_hist(symbol="600070", adjust="hfq", start_date="20230101", end_date="20250101")
        stock_hfq_df = stock_hfq_df[["日期", "开盘", "收盘", "最高", "最低", "成交量"]]
        stock_hfq_df.columns = ["date", "open", "close", "high", "low", "volume"]

        # 通过统一引擎设置 cerebo
        bt_params = BacktraderParams(
            start_date=pd.to_datetime("2024-01-01"),
            end_date=pd.to_datetime("2025-01-01"),
            start_cash=1000000,
            commission_fee=0.001,
            stake=100,
        )
        self.cerebro = setup_cerebro(stock_hfq_df, bt_params)

        # 加载策略配置
        self.strategys = load_strategy("./config/strategy.yaml")
        self.result = None

    def tearDown(self):
        """测试后验证结果"""
        self.assertIsInstance(self.result, pd.DataFrame)
        print(f"测试结果:\n{self.result}")


def run_back_trader(cerebro: bt.Cerebro, strategy: Type[BaseStrategy], **kwargs) -> pd.DataFrame:
    """运行回测（委托给统一引擎的提取逻辑）

    Args:
        cerebro (bt.Cerebro): 回测引擎
        strategy (Type[BaseStrategy]): 策略类
        **kwargs: 策略参数字典，值为单值或 range

    Returns:
        pd.DataFrame: 回测结果
    """
    # 添加优化策略
    cerebro.optstrategy(strategy, **kwargs)

    # 运行回测
    back = cerebro.run(maxcpus=1)

    # 提取结果
    return _extract_results(back, list(kwargs.keys()))
