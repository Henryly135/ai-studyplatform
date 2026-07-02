import { describe, expect, it } from "vitest";

import { PASSWORD_HINT, validatePassword } from "./password";

describe("密码规则工具", () => {
  it("接受符合规则的密码", () => {
    expect(validatePassword("StudyHub!2026")).toBe("");
  });

  it.each([
    ["长度不足", "A1!a"],
    ["缺少小写字母", "STUDYHUB!2026"],
    ["缺少大写字母", "studyhub!2026"],
    ["缺少数字", "StudyHub!"],
    ["缺少特殊字符", "StudyHub2026"],
  ])("拒绝%s的密码", (_label, password) => {
    expect(validatePassword(password)).toContain("密码至少 8 位");
  });

  it("保持可见提示与密码规则一致", () => {
    expect(PASSWORD_HINT).toContain("至少 8 位");
    expect(PASSWORD_HINT).toContain("大小写字母");
    expect(PASSWORD_HINT).toContain("数字");
    expect(PASSWORD_HINT).toContain("特殊字符");
  });
});
