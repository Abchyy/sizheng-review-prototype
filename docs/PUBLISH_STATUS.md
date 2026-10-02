# 发布状态

项目已发布至公开仓库：

https://github.com/Abchyy/sizheng-review-prototype

默认分支为 `main`。用户已明确授权创建和公开发布。仓库包含全部可复现源代码、公开资料摘录、冻结案例及真实 API 结果。密钥、虚拟环境、私有审计数据库和本地工作缓存不纳入 Git。

本地拉取并启动：

```bash
git clone https://github.com/Abchyy/sizheng-review-prototype.git
cd sizheng-review-prototype
python3 -m sizheng verify
python3 -m sizheng serve --offline
```

真实调用可以使用 `python3 scripts/run_with_keys.py serve`，在本地终端隐藏输入密钥。
