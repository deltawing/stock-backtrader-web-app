import logging

import akshare as ak
import pandas as pd
import streamlit as st

from .backtest import run_backtest
from .logs import logger
from .schemas import AkshareParams, BacktraderParams, StrategyBase

logging.getLogger("streamlit.runtime.scriptrunner_utils").setLevel(logging.ERROR)


model_hash_func = lambda x: x.model_dump()


@st.cache_data(hash_funcs={AkshareParams: model_hash_func})
def gen_stock_df(ak_params: AkshareParams) -> pd.DataFrame:
    """生成股票数据

    Args:
        ak_params (AkshareParams): akshare 参数

    Returns:
        pd.DataFrame: 股票历史数据
    """
    df = ak.stock_zh_a_hist(**ak_params.model_dump())
    if not df.empty:
        return df[["日期", "开盘", "收盘", "最高", "最低", "成交量"]]
    return pd.DataFrame()


@st.cache_data(hash_funcs={StrategyBase: model_hash_func, BacktraderParams: model_hash_func})
def run_backtrader(stock_df: pd.DataFrame, strategy: StrategyBase, bt_params: BacktraderParams) -> pd.DataFrame:
    """运行回测（委托给统一引擎）

    Args:
        stock_df (pd.DataFrame): 股票数据
        strategy (StrategyBase): 策略名称和参数
        bt_params (BacktraderParams): 回测参数

    Returns:
        pd.DataFrame: 回测结果
    """
    # 动态导入策略类
    try:
        strategy_cls = getattr(__import__("strategy"), f"{strategy.name}Strategy")
    except (ImportError, AttributeError) as e:
        logger.error(f"策略导入失败: {e}")
        raise ValueError(f"无法找到策略: {strategy.name}Strategy")

    return run_backtest(
        stock_df=stock_df,
        bt_params=bt_params,
        strategy_cls=strategy_cls,
        strategy_params=strategy.params,
    )
