# Sample Review Report

## Summary

本次变更移除了空值保护和请求校验，存在中高风险。

## Findings

- F001 高风险：`displayName` 移除了 `user == null` 保护，但仍直接调用 `user.getName().trim()`。
- F002 中风险：`update` 移除了 `validate(request)`，可能导致非法请求落库。
