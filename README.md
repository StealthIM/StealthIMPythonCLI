# Stealth IM CLI

Stealth IM CLI 是一个基于终端的即时通讯客户端，使用Python编写，提供了安全、私密的群组聊天功能。

## 核心功能

- **终端界面**: 基于Textual框架构建的现代化TUI界面
- **多服务器支持**: 可连接到多个不同的IM服务器
- **群组聊天**: 支持创建和加入群组，进行多人聊天
- **文件传输**: 支持在群组中发送和接收文件
- **消息管理**: 支持消息撤回、历史消息查看
- **用户管理**: 支持用户注册、登录和会话管理
- **离线消息**: 自动缓存消息，支持离线查看
- **数据加密**: 本地数据使用SQLite数据库安全存储

## 安装说明

### 环境要求

- Python 3.8 或更高版本
- pip 包管理器

### 安装步骤

1. 克隆项目代码:
   ```
   git clone <repository-url>
   cd StealthIMPythonCLI
   ```

2. 安装依赖:
   ```
   pip install -r requirements.txt
   ```

3. 运行应用:
   ```
   python src/main.py
   ```

## 使用方法

1. 启动应用后，首先添加并选择一个IM服务器
2. 登录现有账户或注册新账户
3. 加入现有群组或创建新群组
4. 开始聊天、发送文件和管理群组

## 技术架构

### 核心组件

- **Textual**: 用于构建终端用户界面的Python框架
- **StealthIM SDK**: 与IM服务器通信的核心SDK
- **SQLAlchemy**: ORM框架，用于本地数据存储
- **SQLite**: 本地数据库，存储用户、服务器和消息数据

### 项目结构

```
├── src/                 # 主要源代码
│   ├── screens/         # 各个界面屏幕
│   ├── db.py            # 数据库操作模块
│   ├── main.py          # 应用入口点
│   └── ...
├── SDK/                 # StealthIM SDK
├── styles/              # 界面样式文件
├── requirements.txt     # Python依赖列表
└── data/                # 本地数据存储目录
```

### 主要依赖

- textual>=0.19.0
- sqlalchemy>=1.4.0
- platformdirs>=2.5.0

## 许可证

本项目采用GNU Lesser General Public License v2.1许可证。详情请参阅[LICENSE](LICENSE)文件。