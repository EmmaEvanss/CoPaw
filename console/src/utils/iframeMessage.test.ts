import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchAndSetUserName,
  handleUrlOriginParam,
  resetIframeContextForStandalone,
} from "./iframeMessage";
import { useIframeStore } from "../stores/iframeStore";
import { fetchUserInfo } from "../api/modules/userInfo";
import {
  ensureValidToken,
  isExternalTokenEnabled,
} from "../api/externalToken";
import {
  fetchCustomerInfo,
  fetchUserInit,
} from "../api/modules/customerInfo";

vi.mock("../api/modules/userInfo", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../api/modules/userInfo")>();
  return {
    ...actual,
    fetchUserInfo: vi.fn(),
  };
});

vi.mock("../api/externalToken", () => ({
  ensureValidToken: vi.fn(),
  isExternalTokenEnabled: vi.fn(),
}));

vi.mock("../api/modules/customerInfo", () => ({
  fetchCustomerInfo: vi.fn().mockResolvedValue(null),
  fetchUserInit: vi.fn().mockResolvedValue(null),
}));

vi.mock("../api/modules/auth", () => ({
  authApi: {
    sendCronAuth: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockedFetchUserInfo = vi.mocked(fetchUserInfo);
const mockedEnsureValidToken = vi.mocked(ensureValidToken);
const mockedIsExternalTokenEnabled = vi.mocked(isExternalTokenEnabled);
const mockedFetchCustomerInfo = vi.mocked(fetchCustomerInfo);
const mockedFetchUserInit = vi.mocked(fetchUserInit);

describe("fetchAndSetUserName", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    window.history.pushState({}, "", "/");
    [
      "userid",
      "sysid",
      "vbbk",
      "vorgcode",
      "subBranchId",
      "vorglvl",
      "positionID",
      "token",
    ].forEach((name) => {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    });
    useIframeStore.getState().clearContext();
    vi.clearAllMocks();
    mockedIsExternalTokenEnabled.mockReturnValue(false);
    mockedEnsureValidToken.mockResolvedValue("token");
  });

  it("在 userId 缺失时不请求用户信息接口", async () => {
    await expect(fetchAndSetUserName()).resolves.toBe(false);

    expect(mockedFetchUserInfo).not.toHaveBeenCalled();
  });

  it("首次空 userId 返回后，后续 userId 到达仍会请求用户信息", async () => {
    await expect(fetchAndSetUserName()).resolves.toBe(false);

    useIframeStore.getState().setContext({ userId: "80000001" });
    mockedFetchUserInfo.mockResolvedValueOnce({
      code: "SUC0000",
      message: "success",
      result: true,
      data: [{ userName: "张三", pathName: "某企业/总行/生产部" }],
    });

    await expect(fetchAndSetUserName()).resolves.toBe(true);

    expect(mockedFetchUserInfo).toHaveBeenCalledTimes(1);
    expect(mockedFetchUserInfo).toHaveBeenCalledWith("80000001");
    expect(useIframeStore.getState().userName).toBe("张三");
  });

  it("同一个 userId 的并发查询只请求一次接口", async () => {
    useIframeStore.getState().setContext({ userId: "80000001" });
    mockedFetchUserInfo.mockResolvedValueOnce({
      code: "SUC0000",
      message: "success",
      result: true,
      data: [{ userName: "张三", pathName: "某企业/总行/生产部" }],
    });

    const [firstResult, secondResult] = await Promise.all([
      fetchAndSetUserName(),
      fetchAndSetUserName(),
    ]);

    expect(firstResult).toBe(true);
    expect(secondResult).toBe(true);
    expect(mockedFetchUserInfo).toHaveBeenCalledTimes(1);
  });

  it("外部 token 开启时先等待 token，再请求用户信息", async () => {
    const callOrder: string[] = [];
    useIframeStore.getState().setContext({ userId: "80000001" });
    mockedIsExternalTokenEnabled.mockReturnValue(true);
    mockedEnsureValidToken.mockImplementation(async () => {
      callOrder.push("token:start");
      await Promise.resolve();
      callOrder.push("token:end");
      return "token";
    });
    mockedFetchUserInfo.mockImplementation(async () => {
      callOrder.push("user-info");
      return {
        code: "SUC0000",
        message: "success",
        result: true,
        data: [{ userName: "张三", pathName: "某企业/总行/生产部" }],
      };
    });

    await expect(fetchAndSetUserName()).resolves.toBe(true);

    expect(callOrder).toEqual(["token:start", "token:end", "user-info"]);
    expect(mockedEnsureValidToken).toHaveBeenCalledTimes(1);
    expect(mockedFetchUserInfo).toHaveBeenCalledWith("80000001");
  });

  it("用户切换后忽略旧 userId 的异步返回结果", async () => {
    useIframeStore.getState().setContext({ userId: "80000001" });
    mockedFetchUserInfo.mockImplementation(async () => {
      useIframeStore.getState().setContext({ userId: "80000002" });
      return {
        code: "SUC0000",
        message: "success",
        result: true,
        data: [{ userName: "张三", pathName: "某企业/总行/生产部" }],
      };
    });

    await expect(fetchAndSetUserName()).resolves.toBe(false);

    expect(useIframeStore.getState().userId).toBe("80000002");
    expect(useIframeStore.getState().userName).toBeNull();
  });

  it("独立访问时清理残留的 iframe 上下文", () => {
    useIframeStore.getState().setContext({
      userId: "80000001",
      userName: "张三",
      source: "RMASSIST",
      bbk: "100",
      authHeaders: [{ headerName: "token", headerValue: "old" }],
    });

    resetIframeContextForStandalone();

    expect(useIframeStore.getState().userId).toBeNull();
    expect(useIframeStore.getState().userName).toBeNull();
    expect(useIframeStore.getState().source).toBeNull();
    expect(useIframeStore.getState().authHeaders).toEqual([]);
  });

  it("origin=Y 切换 userId 时清空旧 userName", async () => {
    useIframeStore.getState().setContext({
      userId: "80000001",
      userName: "张三",
    });
    window.history.pushState({}, "", "/?origin=Y");
    document.cookie = "userid=80000002; path=/";

    await handleUrlOriginParam();

    expect(useIframeStore.getState().userId).toBe("80000002");
    expect(useIframeStore.getState().userName).toBeNull();
  });

  it("origin=Y 时从 cookie 读取 subBranchId", async () => {
    window.history.pushState({}, "", "/?origin=Y");
    document.cookie = "userid=80000002; path=/";
    document.cookie = "subBranchId=SUB001; path=/";

    await handleUrlOriginParam();

    expect(useIframeStore.getState().subBranchId).toBe("SUB001");
  });

  it("origin=Y 首次进入时不被客户信息接口阻塞用户初始化", async () => {
    window.history.pushState({}, "", "/?origin=Y");
    document.cookie = "userid=80000002; path=/";
    document.cookie = "vbbk=100; path=/";
    document.cookie = "vorgcode=ORG001; path=/";
    document.cookie = "positionID=POS001; path=/";
    mockedFetchCustomerInfo.mockReturnValueOnce(new Promise<null>(() => {}));

    void handleUrlOriginParam();
    await Promise.resolve();

    expect(mockedFetchUserInit).toHaveBeenCalledWith({
      filename: "PROFILE.md",
      text: expect.stringMatching(
        /分行号：100[\s\S]*网点机构编号：ORG001[\s\S]*岗位编号：POS001[\s\S]*客户经理ID：80000002/,
      ),
    });
  });

  it("origin=Y 进入时不使用本地初始化标记跳过接口", async () => {
    window.history.pushState({}, "", "/?origin=Y");
    document.cookie = "userid=80000002; path=/";
    localStorage.setItem("swe-80000002", "exist");

    await handleUrlOriginParam();

    expect(mockedFetchUserInit).toHaveBeenCalledWith({
      filename: "PROFILE.md",
      text: expect.stringContaining("客户经理ID：80000002"),
    });
  });

  it("origin=Y 客户信息未切换用户时只同步 cookie token", async () => {
    window.history.pushState({}, "", "/?origin=Y");
    document.cookie = "userid=80000002; path=/";
    document.cookie = "token=fresh-token; path=/";
    mockedFetchCustomerInfo.mockResolvedValueOnce({
      returnCode: "SUC0000",
      body: {
        output: {
          result: {
            userChange: false,
            sysId: "updated-sys",
            token: "response-token",
            bbk: "updated-bbk",
            orgCode: "updated-org",
            orgLvl: "updated-lvl",
            userId: "updated-user",
            positionId: "updated-position",
          },
        },
      },
    });

    await handleUrlOriginParam();

    expect(useIframeStore.getState()).toMatchObject({
      userId: "80000002",
      token: "fresh-token",
      bbk: null,
      orgCode: null,
      positionId: null,
      userChange: false,
    });
  });

  it("origin=Y 客户信息未切换用户时只初始化一次", async () => {
    window.history.pushState({}, "", "/?origin=Y");
    document.cookie = "userid=80000002; path=/";
    mockedFetchUserInit.mockResolvedValue({ appended: true });
    mockedFetchCustomerInfo.mockResolvedValueOnce({
      returnCode: "SUC0000",
      body: {
        output: {
          result: {
            userChange: false,
            sysId: "sys",
            token: "response-token",
            bbk: "bbk",
            orgCode: "org",
            orgLvl: "lvl",
            userId: "80000002",
            positionId: "position",
          },
        },
      },
    });

    await handleUrlOriginParam();

    expect(mockedFetchUserInit).toHaveBeenCalledTimes(1);
  });
});
