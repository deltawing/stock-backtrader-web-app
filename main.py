#!/usr/bin/env python3
"""stock-backtrader-cli: A股回测 CLI 工具

用法:
  python main.py run --symbol 600519 --start 20240101 --end 20241231
  python main.py run --symbol 600519 --start 20240101 --end 20241231 --strategy MaCross
  python main.py run --symbol 600519 --start 20240101 --end 20241231 --optimize
  python main.py kline --symbol 600519 --start 20260101 --end 20260301

示例:
  python main.py run --symbol 600519 --start 20260101 --end 20260301 --cash 100000 --stake 100
"""

import argparse
import datetime
import sys
from typing import Optional

import akshare as ak
import pandas as pd

from strategy import MaStrategy, MaCrossStrategy
from utils.backtest import run_backtest
from utils.schemas import BacktraderParams
from charts.stock import draw_pro_kline
from charts.results import draw_result_bar


# 策略注册表
STRATEGY_MAP = {
    "Ma": MaStrategy,
    "MaCross": MaCrossStrategy,
}


def fetch_stock_data(symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
    """获取 A 股日线数据

    Args:
        symbol: 股票代码（如 600519）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        adjust: 复权方式，qfq=前复权 hfq=后复权 ""=不复权

    Returns:
        DataFrame: 包含 date/open/close/high/low/volume 列
    """
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    if df.empty:
        print(f"错误: 未获取到 {symbol} 的数据，请检查股票代码和日期范围")
        sys.exit(1)

    df = df[["日期", "开盘", "收盘", "最高", "最低", "成交量"]]
    df["date"] = df["日期"]
    df["open"] = df["开盘"]
    df["close"] = df["收盘"]
    df["high"] = df["最高"]
    df["low"] = df["最低"]
    df["volume"] = df["成交量"]
    return df


def cmd_kline(args: argparse.Namespace):
    """画 K 线图"""
    print(f"获取 {args.symbol} 数据 ({args.start} ~ {args.end}) ...")
    df = fetch_stock_data(args.symbol, args.start, args.end, args.adjust)
    print(f"共 {len(df)} 条记录")

    chart = draw_pro_kline(df)
    output_file = f"kline_{args.symbol}_{args.start}_{args.end}.html"
    chart.render(output_file)
    print(f"K 线图已保存: {output_file}")


def cmd_run(args: argparse.Namespace):
    """运行回测"""
    strategy_name = args.strategy
    if strategy_name not in STRATEGY_MAP:
        print(f"错误: 不支持策略 '{strategy_name}'，可选: {list(STRATEGY_MAP.keys())}")
        sys.exit(1)

    strategy_cls = STRATEGY_MAP[strategy_name]

    print(f"策略:     {strategy_name}")
    print(f"标的:     {args.symbol}")
    print(f"区间:     {args.start} ~ {args.end}")
    print(f"本金:     {args.cash} 元")
    print(f"每笔:     {args.stake} 股")
    print(f"佣金:     {args.commission}")
    print(f"获取数据中 ...")

    df = fetch_stock_data(args.symbol, args.start, args.end, args.adjust)
    print(f"数据: {len(df)} 条记录 ({df['date'].min()} ~ {df['date'].max()})")

    bt_params = BacktraderParams(
        start_date=pd.to_datetime(args.start),
        end_date=pd.to_datetime(args.end),
        start_cash=args.cash,
        commission_fee=args.commission,
        stake=args.stake,
    )

    # 策略参数
    if args.optimize:
        # 参数优化模式：使用配置中的 range
        strategy_params = {
            "maperiod": range(10, 31, 5),
        }
        print("模式: 参数优化")
        print(f"参数搜索: maperiod={list(strategy_params['maperiod'])}")
    else:
        strategy_params = {
            "maperiod": args.maperiod,
        }
        print(f"参数: maperiod={args.maperiod}")

    # 运行回测
    print("运行回测中 ...")
    result = run_backtest(
        stock_df=df,
        bt_params=bt_params,
        strategy_cls=strategy_cls,
        strategy_params=strategy_params,
    )

    print("\n=== 回测结果 ===")
    print(result.to_string(index=False))

    # 保存结果 CSV
    csv_file = f"result_{args.symbol}_{args.start}_{args.end}_{strategy_name}.csv"
    result.to_csv(csv_file, index=False)
    print(f"\n结果已保存: {csv_file}")

    # 如果结果为多行（优化模式），画对比图
    if len(result) > 1:
        chart = draw_result_bar(result)
        chart_file = f"result_{args.symbol}_{args.start}_{args.end}_{strategy_name}.html"
        chart.render(chart_file)
        print(f"结果对比图: {chart_file}")

    # 最佳参数
    best_idx = result["return"].idxmax()
    best = result.loc[best_idx]
    print(f"\n最佳参数: return={best['return']:.2f}%  dd={best['dd']:.2f}%  sharpe={best['sharpe']}")


def main():
    parser = argparse.ArgumentParser(
        description="stock-backtrader-cli - A股回测 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py kline --symbol 600519 --start 20260101 --end 20260301
  python main.py run --symbol 600519 --start 20260101 --end 20260301 --cash 100000 --stake 100
  python main.py run --symbol 600519 --start 20240101 --end 20241231 --strategy MaCross --optimize
        """,
    )
    parser.add_argument("command", choices=["run", "kline"], help="run=回测, kline=画K线图")

    # 通用参数
    parser.add_argument("--symbol", default="600519", help="股票代码，如 600519")
    parser.add_argument("--start", default="20260101", help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default="20260301", help="结束日期 YYYYMMDD")
    parser.add_argument("--adjust", default="qfq", choices=["qfq", "hfq", ""], help="复权方式")

    # 回测参数
    parser.add_argument("--strategy", default="Ma", choices=list(STRATEGY_MAP.keys()), help="策略名")
    parser.add_argument("--cash", type=float, default=100000, help="初始资金")
    parser.add_argument("--stake", type=int, default=100, help="每笔股数")
    parser.add_argument("--commission", type=float, default=0.001, help="佣金费率")
    parser.add_argument("--maperiod", type=int, default=15, help="MA 周期（单次回测模式）")
    parser.add_argument("--optimize", action="store_true", help="参数优化模式")

    args = parser.parse_args()

    if args.command == "kline":
        cmd_kline(args)
    elif args.command == "run":
        cmd_run(args)


if __name__ == "__main__":
    main()
