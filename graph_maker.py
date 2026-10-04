import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# 日本語フォント設定
plt.rcParams['font.family'] = 'Hiragino Sans'

# CSVファイルを読み込む
df = pd.read_csv('課題3.csv')

# 所属ごとの参加者数
dept_count = df['所属'].value_counts()

# 所属ごとの平均スコア
dept_avg = df.groupby('所属')['スコア'].mean()

# ---- 1. 円グラフ ----
fig1, ax1 = plt.subplots(figsize=(7, 7))

ax1.pie(
    dept_count,
    labels=dept_count.index,
    autopct='%1.1f%%',
    startangle=90,
    counterclock=False,
)
ax1.set_title('所属別 参加者数の割合', fontsize=16, pad=20)

fig1.savefig('pie_chart.png', dpi=150, bbox_inches='tight')
print('pie_chart.png を保存しました')

# ---- 2. 棒グラフ ----
fig2, ax2 = plt.subplots(figsize=(8, 6))

bars = ax2.bar(dept_avg.index, dept_avg.values, color=['#4C72B0', '#DD8452', '#55A868'])

# 各棒の上に数値を表示
for bar in bars:
    height = bar.get_height()
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        height + 0.5,
        f'{height:.1f}',
        ha='center', va='bottom', fontsize=12
    )

ax2.set_title('所属別 平均スコア', fontsize=16)
ax2.set_xlabel('所属', fontsize=13)
ax2.set_ylabel('平均スコア', fontsize=13)
ax2.set_ylim(0, 100)
ax2.yaxis.set_major_locator(ticker.MultipleLocator(10))

fig2.savefig('bar_chart.png', dpi=150, bbox_inches='tight')
print('bar_chart.png を保存しました')

# ---- 3. ヒストグラム ----
fig3, ax3 = plt.subplots(figsize=(8, 6))

ax3.hist(df['スコア'], bins=10, range=(0, 100), color='#4C72B0', edgecolor='white', linewidth=0.8)

ax3.set_title('スコア分布', fontsize=16)
ax3.set_xlabel('スコア', fontsize=13)
ax3.set_ylabel('人数', fontsize=13)
ax3.xaxis.set_major_locator(ticker.MultipleLocator(10))
ax3.yaxis.set_major_locator(ticker.MultipleLocator(1))

fig3.savefig('histogram.png', dpi=150, bbox_inches='tight')
print('histogram.png を保存しました')

plt.show()
print('完了')
