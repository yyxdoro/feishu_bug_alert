# 服务器部署触发器设置

推荐在 Linux 服务器上使用 `cron` 定时触发。

## 1. 项目路径

当前服务器项目部署在：

```bash
/home/ec2-user/yuha/feishu_bug_alert
```

脚本入口：

```bash
/home/ec2-user/yuha/feishu_bug_alert/feishu_bug_alert.py
```

Python 虚拟环境：

```bash
/home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3
```

日志目录：

```bash
/home/ec2-user/yuha/feishu_bug_alert/logs
```

## 2. 创建日志目录

```bash
mkdir -p /home/ec2-user/yuha/feishu_bug_alert/logs
```

## 3. 编辑 crontab

```bash
crontab -e
```

添加下面这一行，表示每周一到周五 06:00 执行：

```cron
0 6 * * 1-5 cd /home/ec2-user/yuha/feishu_bug_alert && /home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3 /home/ec2-user/yuha/feishu_bug_alert/feishu_bug_alert.py >> /home/ec2-user/yuha/feishu_bug_alert/logs/cron.log 2>&1
```

如果需要直接替换旧路径，可以先备份再批量替换：

```bash
crontab -l > /tmp/feishu_bug_alert.cron.bak
crontab -l | sed 's#/home/ec2-user/feishu_bug_alert#/home/ec2-user/yuha/feishu_bug_alert#g' | crontab -
```

## 4. 查看是否已写入

```bash
crontab -l
```

确认输出包含：

```cron
0 6 * * 1-5 cd /home/ec2-user/yuha/feishu_bug_alert && /home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3 /home/ec2-user/yuha/feishu_bug_alert/feishu_bug_alert.py >> /home/ec2-user/yuha/feishu_bug_alert/logs/cron.log 2>&1
```

## 5. 手动测试一次

```bash
cd /home/ec2-user/yuha/feishu_bug_alert && /home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3 /home/ec2-user/yuha/feishu_bug_alert/feishu_bug_alert.py
```

## 6. 查看日志

```bash
tail -n 100 /home/ec2-user/yuha/feishu_bug_alert/logs/cron.log
```

## 7. 注意事项

- 服务器时区必须正确，否则 06:00 可能不是你预期的本地时间。
- 用 `date` 检查服务器当前时间。
- 不要把 `app_secret` 提交到公开仓库；生产环境更推荐改成环境变量或服务器私有配置文件。
