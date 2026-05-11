import { request } from "../request";
import type {
  ChannelConfig,
  SingleChannelConfig,
  ChannelDistributionResponse,
} from "../types";

export const channelApi = {
  listChannelTypes: () => request<string[]>("/config/channels/types"),

  listChannels: () => request<ChannelConfig>("/config/channels"),

  updateChannels: (body: ChannelConfig) =>
    request<ChannelConfig>("/config/channels", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getChannelConfig: (channelName: string) =>
    request<SingleChannelConfig>(
      `/config/channels/${encodeURIComponent(channelName)}`,
    ),

  updateChannelConfig: (channelName: string, body: SingleChannelConfig) =>
    request<SingleChannelConfig>(
      `/config/channels/${encodeURIComponent(channelName)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),

  getWeixinQrcode: () =>
    request<{ qrcode_img: string; qrcode: string }>(
      "/config/channels/weixin/qrcode",
    ),

  getWeixinQrcodeStatus: (qrcode: string) =>
    request<{ status: string; bot_token: string; base_url: string }>(
      `/config/channels/weixin/qrcode/status?qrcode=${encodeURIComponent(
        qrcode,
      )}`,
    ),

  listChannelDistributionTenants: () =>
    request<{ tenant_ids: string[] }>(
      "/config/channels/distribution/tenants",
    ),

  distributeChannelConfig: (
    channelName: string,
    body: {
      target_tenant_ids: string[];
      fields?: string[];
      overwrite?: boolean;
    },
  ) =>
    request<ChannelDistributionResponse>(
      `/config/channels/${encodeURIComponent(channelName)}/distribute`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
};
