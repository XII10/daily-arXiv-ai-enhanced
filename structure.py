from pydantic import BaseModel, Field

class Structure(BaseModel):
    tldr: str = Field(description="论文一句话核心摘要")
    motivation: str = Field(description="论文的研究动机与要解决的问题")
    method: str = Field(description="论文使用的核心实验/理论方法")
    result: str = Field(description="论文得到的关键实验结果")
    conclusion: str = Field(description="论文最终得出的核心结论")
