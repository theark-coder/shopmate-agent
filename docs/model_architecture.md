
# Decoder-only Transformer：从输入到 Next Token

## 生成流程

输入文本
→ Tokenizer
→ Token IDs
→ Token Embedding 与位置信息
→ 多层 Transformer Decoder
→ Logits
→ Softmax / 解码策略
→ 下一个 Token
→ 将 Token 追加到序列，继续生成

## 核心概念

- Token：模型处理文本的基本单位，不一定等于一个汉字。
- Embedding 层：把离散 Token ID 映射为连续向量。
- Decoder-only：使用自回归方式逐步生成 Token。
- Causal Mask：当前位置只能关注自己和之前的位置，不能直接读取未来 Token。
- Prompt Tokens：输入消息等内容的 Token 计量。
- Completion Tokens：模型生成输出的 Token 计量。

## 与 ShopMate 的关系

Day 13 的检索 Embedding 用于语义检索。
Day 15 的模型 Embedding 层用于模型内部计算。

ShopMate 的实际 API 用量以服务端返回的 usage 为准，
不用汉字数量估算。
