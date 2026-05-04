"""统一回测引擎

整合 processing.py 和 tests/base_test.py 的回测逻辑。
支持单次回测和参数优化两种模式。
"""

from typing import Any, Dict, Optional, Type

import backtrader as bt
import backtrader.analyzers as btanalyzers
import pandas as pd

from .schemas import BacktraderParams
from strategy.base import BaseStrategy


def setup_cerebro(
    stock_df: pd.DataFrame,
    bt_params: BacktraderParams,
) -> bt.Cerebro:
    """配置回测引擎，通用设置

    Args:
        stock_df: DataFrame, 必须包含 date/open/close/high/low/volume 列
        bt_params: 回测参数

    Returns:
        bt.Cerebro: 配置好的回测引擎
    """
    # 设置日期索引
    stock_df = stock_df.copy()
    stock_df.index = pd.to_datetime(stock_df["date"])

    # 创建数据源
    data = bt.feeds.PandasData(
        dataname=stock_df,
        fromdate=bt_params.start_date,
        todate=bt_params.end_date,
    )

    # 初始化回测引擎
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.broker.setcash(bt_params.start_cash)
    cerebro.broker.setcommission(commission=bt_params.commission_fee)
    cerebro.addsizer(bt.sizers.FixedSize, stake=bt_params.stake)

    # 添加分析器
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(btanalyzers.Returns, _name="returns")

    return cerebro


def _extract_results(back: list, param_keys: list[str]) -> pd.DataFrame:
    """从回测结果中提取性能指标

    Args:
        back: cerebro.run() 的结果
        param_keys: 策略参数名列表

    Returns:
        pd.DataFrame: 包含参数组合和对应 performance 指标
    """
    par_list = []
    for x in back:
        # 收集策略参数
        par = []
        for key in param_keys:
            par.append(x[0].params._getkwargs()[key])

        # 添加性能指标
        par.extend(
            [
                x[0].analyzers.returns.get_analysis()["rnorm100"],
                x[0].analyzers.drawdown.get_analysis()["max"]["drawdown"],
                x[0].analyzers.sharpe.get_analysis()["sharperatio"],
            ]
        )
        par_list.append(par)

    # 创建结果数据框
    columns = list(param_keys)
    columns.extend(["return", "dd", "sharpe"])
    par_df = pd.DataFrame(par_list, columns=columns)
    return par_df


def run_backtest(
    stock_df: pd.DataFrame,
    bt_params: BacktraderParams,
    strategy_cls: Type[BaseStrategy],
    strategy_params: Optional[Dict[str, Any]] = None,
    maxcpus: Optional[int] = None,
) -> pd.DataFrame:
    """运行回测，支持单次或参数优化

    Args:
        stock_df: 股票数据，必须包含 date/open/close/high/low/volume 列
        bt_params: 回测参数
        strategy_cls: 策略类
        strategy_params: 策略参数字典。
            - 值为单值（如 {"maperiod": 15}）→ 单次回测
            - 值为 range/list（如 {"maperiod": range(10, 31)}）→ 参数优化
        maxcpus: 并行 CPU 数，默认 None（不限），测试环境建议 1

    Returns:
        pd.DataFrame: 包含参数组合和 return/dd/sharpe 指标
    """
    param_keys = list((strategy_params or {}).keys())

    # 配置回测引擎
    cerebro = setup_cerebro(stock_df, bt_params)

    # 添加策略
    if strategy_params:
        cerebro.optstrategy(strategy_cls, **strategy_params)
    else:
        cerebro.optstrategy(strategy_cls)

    # 运行回测
    run_kwargs = {}
    if maxcpus is not None:
        run_kwargs["maxcpus"] = maxcpus
    back = cerebro.run(**run_kwargs)

    # 提取结果
    return _extract_results(back, param_keys)
