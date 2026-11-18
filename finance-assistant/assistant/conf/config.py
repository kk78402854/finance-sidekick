"""
这个模块作用：读取.env文件内容
"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 找到.env文件位置 ，当前模块相对位置
ENV_DIR = Path(__file__).parents[2]
ENV_FILE = ENV_DIR / '.env'

# 第一种方式
# os.getenv("key")
# 第二种 pydantic-settings
# 1 创建类，继承pydantic-settings类
class Settings(BaseSettings):
    # 2 调用封装对象读取.env文件内容
    # 到传入.env文件读取内容，把内容读取赋值到对应属性里面
    #* 要求对象起名字，名称必须固定 model_config
    model_config = SettingsConfigDict(
        # env文件位置
        env_file=ENV_FILE,
        # env文件编码
        env_file_encoding='utf-8',
        # 当前类属性数量是否与配置文件一致
        extra='ignore'
    )
    # 不区分大小写
    LLM_MODEL: str
    llm_api_key: str
    llm_base_url: str
    # 数据库
    database_url: str
    # 金融中台 API
    finance_api_base_url: str = "http://127.0.0.1:8000"
    # 渠道编码，必须存在于 dim_channel
    finance_channel_code: str = "MOBILE_BANK"
    # 员工编号，工单类接口需要，必须存在于 dim_employee
    finance_operator_no: str = "EMP000001"
    # 演示客户号，正式环境应由登录态映射得到
    demo_customer_no: str = "CUS00000001"
    # 知识库检索服务，可为空，为空时 RAG 返回空结果
    finance_rag_base_url: str = ""
    # 中台业务库只读连接，管理端列表/大盘用；为空时管理端列表接口不可用
    finance_db_url: str = ""
    # 服务器
    app_host: str
    app_port: int

# 创建Settings对象
settings = Settings()

if __name__ == '__main__':
    print(settings.LLM_MODEL)
    print(settings.llm_api_key)
