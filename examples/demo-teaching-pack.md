# 第三章 相互作用力 · 题包示例

本文件演示 `examples/ok-teaching-pack.json` 里的自定义语法。把那份 JSON 贴进 md2pdf 的
「设置 → 智能扩展 → 自定义扩展 → 应用扩展」，再打开本文件看效果。

## 一、行内语法

受力分析先定研究对象[[t:整体法]]，再逐个拆开[[t:隔离法]]；{易错:漏掉摩擦力与弹力的顺序}。

几个常用近似：$g$ 取 $9.8\\ \\mathrm{m/s^2}$，等等...（这三个点会被扩展换成省略号）

## 二、围栏块

```tb-tip
提示块里可以写 **Markdown**、列表、公式：

- 先画受力图
- 再列平衡方程 $\\sum F = 0$

图形也能嵌（内层围栏换 `~~~` 标记）：

~~~svg
<svg width="300" height="90" viewBox="0 0 300 90" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="1" width="298" height="88" rx="10" fill="#eef3ff" stroke="#2f6fed" stroke-width="2"/>
  <text x="150" y="52" font-size="15" text-anchor="middle" fill="#1d4ed8">$content 里可以画图</text>
</svg>
~~~
```

```tb-warn
- 滑动摩擦力 $f = \\mu N$ 里的 $N$ 是**正压力**，不是重力
- 静摩擦力的方向要和「相对运动趋势」反着看
```

```tb-ans
**解**：对整体列方程

$$
F - \\mu (m_1 + m_2) g = (m_1 + m_2) a
$$

得 $a = 2.0\\ \\mathrm{m/s^2}$，方向向右。
```

## 三、打印检查

打印预览里，卡片不应被切两页（样式里有 `break-inside:avoid`）；
底色需要在打印界面勾「背景图形」才会印出来。
