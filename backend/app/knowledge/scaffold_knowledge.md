# Scaffold Knowledge

## AgentScope 2.0 事件与消息

AgentScope 2.0 的核心循环可以理解成：用户输入变成消息，Agent 用模型、上下文、工具和中间件推进一轮执行，执行过程不断产生 AgentEvent，最后把结果流式返回给用户或前端协议层。

## RAG 与 Tool Group

在当前学习阶段，RAG 更适合作为 tool 或 tool group 接入 Agent。检索、重排、引用整理、权限过滤都可以独立成工具边界，Agent 通过工具结果组织回答。

## Context 与短期记忆

Context 承担短期记忆和上下文管理能力。长期记忆可以暂时放一放，等业务闭环清楚后，再通过 Content Offload、外部存储或专门记忆服务接入。

## Agent Service

Agent Service 更像可运行的服务壳和工程化入口，不只是脚手架。它提供 agent、session、credential、workspace、schedule、chat 等 API，适合先跑起来看效果，再把业务工具、权限、观测和存储逐步装进去。
