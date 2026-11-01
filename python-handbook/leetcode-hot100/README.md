# 力扣 Hot 100 全解题解集（Python 3 · 教学导向）

> 题单基准日：**2026-09-27**——当日通过 leetcode.cn GraphQL API 实抓 `top-100-liked` 题单逐题核对：**共 100 题、17 个官方专题**；难度分布 **简单 20 / 中等 68 / 困难 12**。
>
> 每题统一四件套：**① 题意速览 → ② 思路讲解 → ③ 注释代码 → ④ 复杂度 · 易错点 · 面试追问**。代码全部为 Python 3、LeetCode 提交格式、中文注释（注释讲机制与不变量，不翻译代码）。英文术语首次出现处均标注中文解释。

## 一、文件总览（12 个文件覆盖 17 个官方专题）

| 文件 | 覆盖官方专题 | 题数 |
|---|---|---|
| [01-哈希与双指针.md](01-哈希与双指针.md) | 哈希 · 双指针 | 7 |
| [02-滑动窗口与子串.md](02-滑动窗口与子串.md) | 滑动窗口 · 子串 | 5 |
| [03-数组与矩阵.md](03-数组与矩阵.md) | 普通数组 · 矩阵 | 9 |
| [04-链表.md](04-链表.md) | 链表 | 14 |
| [05-二叉树.md](05-二叉树.md) | 二叉树 | 15 |
| [06-图论.md](06-图论.md) | 图论 | 4 |
| [07-回溯.md](07-回溯.md) | 回溯 | 8 |
| [08-二分查找.md](08-二分查找.md) | 二分查找 | 6 |
| [09-栈与堆.md](09-栈与堆.md) | 栈 · 堆 | 8 |
| [10-贪心.md](10-贪心.md) | 贪心算法 | 4 |
| [11-动态规划.md](11-动态规划.md) | 动态规划 · 多维动态规划 | 15 |
| [12-技巧.md](12-技巧.md) | 技巧 | 5 |

每个文件开头有「套路总览」表（本题解文件全部题目的一句话核心），可当**二刷自测清单**用：遮住题解只看表，想得起思路就过，想不起再进四件套。

## 二、难度分布

| 难度 | 题数 |
|---|---|
| 简单 | 20 |
| 中等 | 68 |
| 困难 | 12 |

12 道困难题：42 接雨水、76 最小覆盖子串、239 滑动窗口最大值、41 缺失的第一个正数、25 K 个一组翻转链表、23 合并 K 个升序链表、124 二叉树中的最大路径和、51 N 皇后、4 寻找两个正序数组的中位数、84 柱状图中最大的矩形、295 数据流的中位数、32 最长有效括号。每道困难题的四件套里都给了"先写好想的版本拿稳分，再升级最优解"的路线。

## 三、17 个官方专题导航

### 1. 哈希（3 题）→ [01-哈希与双指针.md](01-哈希与双指针.md)

| # | 题目 | 难度 |
|---|---|---|
| 1 | [两数之和](https://leetcode.cn/problems/two-sum/) | 简单 |
| 49 | [字母异位词分组](https://leetcode.cn/problems/group-anagrams/) | 中等 |
| 128 | [最长连续序列](https://leetcode.cn/problems/longest-consecutive-sequence/) | 中等 |

### 2. 双指针（4 题）→ [01-哈希与双指针.md](01-哈希与双指针.md)

| # | 题目 | 难度 |
|---|---|---|
| 283 | [移动零](https://leetcode.cn/problems/move-zeroes/) | 简单 |
| 11 | [盛最多水的容器](https://leetcode.cn/problems/container-with-most-water/) | 中等 |
| 15 | [三数之和](https://leetcode.cn/problems/3sum/) | 中等 |
| 42 | [接雨水](https://leetcode.cn/problems/trapping-rain-water/) | 困难 |

### 3. 滑动窗口（2 题）→ [02-滑动窗口与子串.md](02-滑动窗口与子串.md)

| # | 题目 | 难度 |
|---|---|---|
| 3 | [无重复字符的最长子串](https://leetcode.cn/problems/longest-substring-without-repeating-characters/) | 中等 |
| 438 | [找到字符串中所有字母异位词](https://leetcode.cn/problems/find-all-anagrams-in-a-string/) | 中等 |

### 4. 子串（3 题）→ [02-滑动窗口与子串.md](02-滑动窗口与子串.md)

| # | 题目 | 难度 |
|---|---|---|
| 560 | [和为 K 的子数组](https://leetcode.cn/problems/subarray-sum-equals-k/) | 中等 |
| 239 | [滑动窗口最大值](https://leetcode.cn/problems/sliding-window-maximum/) | 困难 |
| 76 | [最小覆盖子串](https://leetcode.cn/problems/minimum-window-substring/) | 困难 |

### 5. 普通数组（5 题）→ [03-数组与矩阵.md](03-数组与矩阵.md)

| # | 题目 | 难度 |
|---|---|---|
| 53 | [最大子数组和](https://leetcode.cn/problems/maximum-subarray/) | 中等 |
| 56 | [合并区间](https://leetcode.cn/problems/merge-intervals/) | 中等 |
| 189 | [轮转数组](https://leetcode.cn/problems/rotate-array/) | 中等 |
| 238 | [除了自身以外数组的乘积](https://leetcode.cn/problems/product-of-array-except-self/) | 中等 |
| 41 | [缺失的第一个正数](https://leetcode.cn/problems/first-missing-positive/) | 困难 |

### 6. 矩阵（4 题）→ [03-数组与矩阵.md](03-数组与矩阵.md)

| # | 题目 | 难度 |
|---|---|---|
| 73 | [矩阵置零](https://leetcode.cn/problems/set-matrix-zeroes/) | 中等 |
| 54 | [螺旋矩阵](https://leetcode.cn/problems/spiral-matrix/) | 中等 |
| 48 | [旋转图像](https://leetcode.cn/problems/rotate-image/) | 中等 |
| 240 | [搜索二维矩阵 II](https://leetcode.cn/problems/search-a-2d-matrix-ii/) | 中等 |

### 7. 链表（14 题）→ [04-链表.md](04-链表.md)

| # | 题目 | 难度 |
|---|---|---|
| 160 | [相交链表](https://leetcode.cn/problems/intersection-of-two-linked-lists/) | 简单 |
| 206 | [反转链表](https://leetcode.cn/problems/reverse-linked-list/) | 简单 |
| 234 | [回文链表](https://leetcode.cn/problems/palindrome-linked-list/) | 简单 |
| 141 | [环形链表](https://leetcode.cn/problems/linked-list-cycle/) | 简单 |
| 142 | [环形链表 II](https://leetcode.cn/problems/linked-list-cycle-ii/) | 中等 |
| 21 | [合并两个有序链表](https://leetcode.cn/problems/merge-two-sorted-lists/) | 简单 |
| 2 | [两数相加](https://leetcode.cn/problems/add-two-numbers/) | 中等 |
| 19 | [删除链表的倒数第 N 个结点](https://leetcode.cn/problems/remove-nth-node-from-end-of-list/) | 中等 |
| 24 | [两两交换链表中的节点](https://leetcode.cn/problems/swap-nodes-in-pairs/) | 中等 |
| 25 | [K 个一组翻转链表](https://leetcode.cn/problems/reverse-nodes-in-k-group/) | 困难 |
| 138 | [随机链表的复制](https://leetcode.cn/problems/copy-list-with-random-pointer/) | 中等 |
| 148 | [排序链表](https://leetcode.cn/problems/sort-list/) | 中等 |
| 23 | [合并 K 个升序链表](https://leetcode.cn/problems/merge-k-sorted-lists/) | 困难 |
| 146 | [LRU 缓存](https://leetcode.cn/problems/lru-cache/) | 中等 |

### 8. 二叉树（15 题）→ [05-二叉树.md](05-二叉树.md)

| # | 题目 | 难度 |
|---|---|---|
| 94 | [二叉树的中序遍历](https://leetcode.cn/problems/binary-tree-inorder-traversal/) | 简单 |
| 104 | [二叉树的最大深度](https://leetcode.cn/problems/maximum-depth-of-binary-tree/) | 简单 |
| 226 | [翻转二叉树](https://leetcode.cn/problems/invert-binary-tree/) | 简单 |
| 101 | [对称二叉树](https://leetcode.cn/problems/symmetric-tree/) | 简单 |
| 543 | [二叉树的直径](https://leetcode.cn/problems/diameter-of-binary-tree/) | 简单 |
| 102 | [二叉树的层序遍历](https://leetcode.cn/problems/binary-tree-level-order-traversal/) | 中等 |
| 108 | [将有序数组转换为二叉搜索树](https://leetcode.cn/problems/convert-sorted-array-to-binary-search-tree/) | 简单 |
| 98 | [验证二叉搜索树](https://leetcode.cn/problems/validate-binary-search-tree/) | 中等 |
| 230 | [二叉搜索树中第 K 小的元素](https://leetcode.cn/problems/kth-smallest-element-in-a-bst/) | 中等 |
| 199 | [二叉树的右视图](https://leetcode.cn/problems/binary-tree-right-side-view/) | 中等 |
| 114 | [二叉树展开为链表](https://leetcode.cn/problems/flatten-binary-tree-to-linked-list/) | 中等 |
| 105 | [从前序与中序遍历序列构造二叉树](https://leetcode.cn/problems/construct-binary-tree-from-preorder-and-inorder-traversal/) | 中等 |
| 437 | [路径总和 III](https://leetcode.cn/problems/path-sum-iii/) | 中等 |
| 236 | [二叉树的最近公共祖先](https://leetcode.cn/problems/lowest-common-ancestor-of-a-binary-tree/) | 中等 |
| 124 | [二叉树中的最大路径和](https://leetcode.cn/problems/binary-tree-maximum-path-sum/) | 困难 |

### 9. 图论（4 题）→ [06-图论.md](06-图论.md)

| # | 题目 | 难度 |
|---|---|---|
| 200 | [岛屿数量](https://leetcode.cn/problems/number-of-islands/) | 中等 |
| 994 | [腐烂的橘子](https://leetcode.cn/problems/rotting-oranges/) | 中等 |
| 207 | [课程表](https://leetcode.cn/problems/course-schedule/) | 中等 |
| 208 | [实现 Trie (前缀树)](https://leetcode.cn/problems/implement-trie-prefix-tree/) | 中等 |

### 10. 回溯（8 题）→ [07-回溯.md](07-回溯.md)

| # | 题目 | 难度 |
|---|---|---|
| 46 | [全排列](https://leetcode.cn/problems/permutations/) | 中等 |
| 78 | [子集](https://leetcode.cn/problems/subsets/) | 中等 |
| 17 | [电话号码的字母组合](https://leetcode.cn/problems/letter-combinations-of-a-phone-number/) | 中等 |
| 39 | [组合总和](https://leetcode.cn/problems/combination-sum/) | 中等 |
| 22 | [括号生成](https://leetcode.cn/problems/generate-parentheses/) | 中等 |
| 79 | [单词搜索](https://leetcode.cn/problems/word-search/) | 中等 |
| 131 | [分割回文串](https://leetcode.cn/problems/palindrome-partitioning/) | 中等 |
| 51 | [N 皇后](https://leetcode.cn/problems/n-queens/) | 困难 |

### 11. 二分查找（6 题）→ [08-二分查找.md](08-二分查找.md)

| # | 题目 | 难度 |
|---|---|---|
| 35 | [搜索插入位置](https://leetcode.cn/problems/search-insert-position/) | 简单 |
| 74 | [搜索二维矩阵](https://leetcode.cn/problems/search-a-2d-matrix/) | 中等 |
| 34 | [在排序数组中查找元素的第一个和最后一个位置](https://leetcode.cn/problems/find-first-and-last-position-of-element-in-sorted-array/) | 中等 |
| 33 | [搜索旋转排序数组](https://leetcode.cn/problems/search-in-rotated-sorted-array/) | 中等 |
| 153 | [寻找旋转排序数组中的最小值](https://leetcode.cn/problems/find-minimum-in-rotated-sorted-array/) | 中等 |
| 4 | [寻找两个正序数组的中位数](https://leetcode.cn/problems/median-of-two-sorted-arrays/) | 困难 |

### 12. 栈（5 题）→ [09-栈与堆.md](09-栈与堆.md)

| # | 题目 | 难度 |
|---|---|---|
| 20 | [有效的括号](https://leetcode.cn/problems/valid-parentheses/) | 简单 |
| 155 | [最小栈](https://leetcode.cn/problems/min-stack/) | 中等 |
| 394 | [字符串解码](https://leetcode.cn/problems/decode-string/) | 中等 |
| 739 | [每日温度](https://leetcode.cn/problems/daily-temperatures/) | 中等 |
| 84 | [柱状图中最大的矩形](https://leetcode.cn/problems/largest-rectangle-in-histogram/) | 困难 |

### 13. 堆（3 题）→ [09-栈与堆.md](09-栈与堆.md)

| # | 题目 | 难度 |
|---|---|---|
| 215 | [数组中的第K个最大元素](https://leetcode.cn/problems/kth-largest-element-in-an-array/) | 中等 |
| 347 | [前 K 个高频元素](https://leetcode.cn/problems/top-k-frequent-elements/) | 中等 |
| 295 | [数据流的中位数](https://leetcode.cn/problems/find-median-from-data-stream/) | 困难 |

### 14. 贪心算法（4 题）→ [10-贪心.md](10-贪心.md)

| # | 题目 | 难度 |
|---|---|---|
| 121 | [买卖股票的最佳时机](https://leetcode.cn/problems/best-time-to-buy-and-sell-stock/) | 简单 |
| 55 | [跳跃游戏](https://leetcode.cn/problems/jump-game/) | 中等 |
| 45 | [跳跃游戏 II](https://leetcode.cn/problems/jump-game-ii/) | 中等 |
| 763 | [划分字母区间](https://leetcode.cn/problems/partition-labels/) | 中等 |

### 15. 动态规划（10 题）→ [11-动态规划.md](11-动态规划.md)

| # | 题目 | 难度 |
|---|---|---|
| 70 | [爬楼梯](https://leetcode.cn/problems/climbing-stairs/) | 简单 |
| 118 | [杨辉三角](https://leetcode.cn/problems/pascals-triangle/) | 简单 |
| 198 | [打家劫舍](https://leetcode.cn/problems/house-robber/) | 中等 |
| 279 | [完全平方数](https://leetcode.cn/problems/perfect-squares/) | 中等 |
| 322 | [零钱兑换](https://leetcode.cn/problems/coin-change/) | 中等 |
| 139 | [单词拆分](https://leetcode.cn/problems/word-break/) | 中等 |
| 300 | [最长递增子序列](https://leetcode.cn/problems/longest-increasing-subsequence/) | 中等 |
| 152 | [乘积最大子数组](https://leetcode.cn/problems/maximum-product-subarray/) | 中等 |
| 416 | [分割等和子集](https://leetcode.cn/problems/partition-equal-subset-sum/) | 中等 |
| 32 | [最长有效括号](https://leetcode.cn/problems/longest-valid-parentheses/) | 困难 |

### 16. 多维动态规划（5 题）→ [11-动态规划.md](11-动态规划.md)

| # | 题目 | 难度 |
|---|---|---|
| 62 | [不同路径](https://leetcode.cn/problems/unique-paths/) | 中等 |
| 64 | [最小路径和](https://leetcode.cn/problems/minimum-path-sum/) | 中等 |
| 5 | [最长回文子串](https://leetcode.cn/problems/longest-palindromic-substring/) | 中等 |
| 1143 | [最长公共子序列](https://leetcode.cn/problems/longest-common-subsequence/) | 中等 |
| 72 | [编辑距离](https://leetcode.cn/problems/edit-distance/) | 中等 |

### 17. 技巧（5 题）→ [12-技巧.md](12-技巧.md)

| # | 题目 | 难度 |
|---|---|---|
| 136 | [只出现一次的数字](https://leetcode.cn/problems/single-number/) | 简单 |
| 169 | [多数元素](https://leetcode.cn/problems/majority-element/) | 简单 |
| 75 | [颜色分类](https://leetcode.cn/problems/sort-colors/) | 中等 |
| 31 | [下一个排列](https://leetcode.cn/problems/next-permutation/) | 中等 |
| 287 | [寻找重复数](https://leetcode.cn/problems/find-the-duplicate-number/) | 中等 |

## 四、14 天刷题路线

每天 5-9 题、合计 100 题；困难题当天想不出就先看题解再独立复写一遍。相邻的题按"同套路"成组，刷完一组立刻能互相印证。

| 天 | 主题 | 题号 | 当日要点 |
|---|---|---|---|
| 1 | 哈希 + 双指针 | 1, 49, 128, 283, 11, 15, 42 | 7 题。抓两个母题：哈希"先查后存"、双指针"淘汰不优组合"。42 接雨水想不出直接看题解，别恋战 |
| 2 | 滑动窗口 + 子串 | 3, 438, 560, 239, 76 | 5 题。两道困难（239/76）都在这天；560 的"前缀和 + 哈希"与 Day 1 的两数之和同构 |
| 3 | 普通数组 + 矩阵 | 53, 56, 189, 238, 41, 73, 54, 48, 240 | 9 题。41 缺失的第一个正数是"原地哈希"经典，耐心啃 |
| 4 | 链表（上）· 指针基本功 | 160, 206, 234, 141, 142, 21, 2 | 7 题。把虚拟头节点（dummy node）和快慢指针两个工具练成肌肉记忆 |
| 5 | 链表（下）· 综合 | 19, 24, 25, 138, 148, 23, 146 | 7 题。146 LRU 缓存是面试出现率最高的题之一，双向链表 + 哈希要能白板手写 |
| 6 | 二叉树（上）· 遍历与深度 | 94, 104, 226, 101, 543, 102, 108, 98 | 8 题。递归三要素（函数定义/基线条件/递归调用）+ BFS 层序，骨架题 |
| 7 | 二叉树（下）· 构造与路径 | 230, 199, 114, 105, 437, 236, 124 | 7 题。124 二叉树中的最大路径和收尾，体会"返回值/记录值分工" |
| 8 | 图论 + 回溯（上） | 200, 994, 207, 208, 46, 78, 17, 39 | 8 题。网格 DFS（矩阵就是隐式图）连着回溯 DFS 练，一脉相承 |
| 9 | 回溯（下）+ 二分（上） | 22, 79, 131, 51, 35, 74, 34 | 7 题。回溯收尾后转入二分；34 题是二分边界模板的试金石 |
| 10 | 二分（下）+ 栈（上） | 33, 153, 4, 20, 155, 394 | 6 题。4 寻找两个正序数组的中位数是全书最难关之一，允许先背模板后消化 |
| 11 | 栈（下）+ 堆 + 贪心（上） | 739, 84, 215, 347, 295, 121, 55 | 7 题。单调栈 + 快速选择 + 对顶堆三个重套路同日到场 |
| 12 | 贪心（下）+ 技巧 | 45, 763, 136, 169, 75, 31, 287 | 7 题。287 一题双解（Floyd 判圈 / 二分值域），收官轻快 |
| 13 | 动态规划（一）· 入门与线性 | 70, 118, 198, 279, 322, 139, 300 | 7 题。从爬楼梯到 LIS，反复抓 DP 三件套：状态定义 → 转移方程 → 初始化与顺序 |
| 14 | 动态规划（二）· 背包与二维 | 152, 416, 32, 62, 64, 5, 1143, 72 | 8 题。完赛！之后建议留 1-2 天，只看各文件「套路总览」表二刷错题 |

## 五、这套题解怎么用

1. **先自己想，再看 ②**：打开题目后先画图/写暴力，卡 15-20 分钟再看思路讲解——② 的价值在于给你"从你的朴素想法到最优解之间缺的那几步"，跳过思考直接读会变成背题。
2. **盯住不变量（Invariant，循环每一步都保持为真的性质）**：双指针、滑动窗口、链表类题目的正确性都压在不变量上。读完代码先遮住注释，自己复述一遍"循环任意时刻什么东西是真的"，复述不出来就是没懂。
3. **④ 当自测题**：易错点先猜后看；面试追问动手写（或至少口述）再对照一句话答法。
4. **套路迁移是主线**：每个 ② 的结尾都指向同家族题，按迁移线连刷（如 1 → 15 → 560）比按专题顺序刷记得更牢。
5. **代码规范**：全部代码可直接提交 LeetCode（`List`/`Optional` 等类型由平台自动导入，树/链表节点由平台提供）；注释中文、讲机制；需要额外导入时（`collections`/`heapq`）代码块里已写明。
6. **术语标注**：英文术语首次出现处用括号标中文（如 LRU（Least Recently Used，最近最少使用）），各文件末尾附本文件术语表。
