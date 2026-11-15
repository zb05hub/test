# 国王与大臣 · 双王棋

运行需要 Python 3.10 或更高版本，无第三方依赖：

```powershell
python server.py --admin 管理员
python server.py
```

第一条命令仅在初始化时运行，执行后按提示输入自选密码。打开 http://127.0.0.1:8000 选择模式，登录后即可开局。界面以 1280 × 720 为固定设计尺寸，随窗口等比缩放；行棋记录分页，页面无需滚动。双人模式在同一台设备轮流操作；人机模式可以执任一方。管理员登录后可查看注册用户。昵称、加盐 scrypt 密码散列及登录会话存于 SQLite；对局留在服务进程内存中，新开局或重启会丢失旧对局。

棋盘由 37 个交点和图 2 的线段组成。后端按相邻边验证普通移动，跳吃需要同一横线或竖线上的两条连续边。规则图第 3 条的备用“黑棋”按第 2、5、6 条解释为白棋；第 6 条解释为有备用大臣时每个大臣回合都添子（不取决于国王是否吃子）。程序以无合法着法作为可检测的困局条件，没有自行增设重复局面或认输规则。两方各计时 40 分钟。

Python 智能体与玩家共享着法生成及判胜函数，使用四层极大极小搜索和 Alpha–Beta 剪枝。局面评价参考吃子数量、国王行动空间和可跳吃机会。它是规则与搜索智能体，无需训练数据。

## 部署到 GitHub Pages

GitHub Pages 只发布网页文件。账号、SQLite 和 Python 智能体需要独立的后端站点。推送到 GitHub 时使用浏览器授权、SSH 或访问令牌。不要把 GitHub 密码、管理员密码或令牌放进仓库或工作流变量。

1. 准备带 HTTPS 入口和持久磁盘的 Python 主机。设置 `GAME_DB` 为持久路径，创建管理员，再以 `python server.py --host 0.0.0.0` 启动。由主机提供 TLS、请求限速和进程守护；当前内存对局要求单进程运行。
2. 设置后端环境变量 `GAME_WEB_ORIGIN` 为前端 origin，例如 `https://你的用户名.github.io`，不含仓库路径或末尾斜杠。
3. 把代码推到 GitHub 仓库的 `main`。在仓库 **Settings → Pages** 选择 **GitHub Actions**；在 **Settings → Secrets and variables → Actions → Variables** 中添加 `GAME_API_URL`，值为后端 HTTPS origin。
4. 在 **Actions → Publish frontend** 运行工作流。成功后，Pages 设置和工作流部署结果将显示实际网址。前端与 API 两端均须保持可用。不要上传 SQLite 文件。

同一 Python 主机也可以直接托管前端和后端，此时无需 GitHub Pages 或跨域配置。
