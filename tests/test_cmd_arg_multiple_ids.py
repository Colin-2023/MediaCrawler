"""Regression coverage for multiline IDs passed from the WebUI to the CLI."""

from unittest.mock import AsyncMock

import config
import pytest

from api.schemas import CrawlerStartRequest
from api.services.crawler_manager import CrawlerManager
from cmd_arg import parse_cmd
from media_platform.bilibili.core import BilibiliCrawler


@pytest.fixture(autouse=True)
def isolate_config(monkeypatch):
    # parse_cmd mutates global configuration; restore every config value afterwards.
    for name, value in vars(config).copy().items():
        if name.isupper():
            monkeypatch.setattr(config, name, value)


@pytest.mark.asyncio
@pytest.mark.parametrize("separator", ["\n", "\r\n", ",", ",\n"])
async def test_webui_multiple_urls_reach_each_videos_comments(monkeypatch, separator):
    bvids = ["BV1d54y1g7db", "BV1dwuKzmE26"]
    urls = [f"https://www.bilibili.com/video/{bvid}/?p=1" for bvid in bvids]
    request = CrawlerStartRequest(
        platform="bili", crawler_type="detail", specified_ids=separator.join(urls)
    )
    command = CrawlerManager()._build_command(request)
    await parse_cmd(command[4:])
    assert config.BILI_SPECIFIED_ID_LIST == urls

    crawler = BilibiliCrawler()
    details = [{"View": {"aid": aid}} for aid in [101, 202]]
    get_details = AsyncMock(side_effect=details)
    comments = AsyncMock()
    monkeypatch.setattr(crawler, "get_video_info_task", get_details)
    monkeypatch.setattr(crawler, "get_comments", comments)
    monkeypatch.setattr(crawler, "download_media", AsyncMock())
    monkeypatch.setattr("media_platform.bilibili.core.bilibili_store.update_bilibili_video", AsyncMock())
    monkeypatch.setattr("media_platform.bilibili.core.bilibili_store.update_up_info", AsyncMock())

    await crawler.get_specified_videos(config.BILI_SPECIFIED_ID_LIST)

    assert [call.kwargs["bvid"] for call in get_details.await_args_list] == bvids
    assert [call.args[0] for call in comments.await_args_list] == [101, 202]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform", "config_name"),
    [
        ("xhs", "XHS_SPECIFIED_NOTE_URL_LIST"),
        ("bili", "BILI_SPECIFIED_ID_LIST"),
        ("dy", "DY_SPECIFIED_ID_LIST"),
        ("wb", "WEIBO_SPECIFIED_ID_LIST"),
        ("ks", "KS_SPECIFIED_ID_LIST"),
        ("tieba", "TIEBA_SPECIFIED_ID_LIST"),
        ("zhihu", "ZHIHU_SPECIFIED_ID_LIST"),
    ],
)
async def test_detail_ids_support_mixed_separators_and_ignore_empty_entries(platform, config_name):
    await parse_cmd([
        "--platform", platform, "--type", "detail", "--specified_id",
        " 123 \r\n\n 456,\n 789 \n, ",
    ])
    assert getattr(config, config_name) == ["123", "456", "789"]


@pytest.mark.asyncio
async def test_creator_ids_support_multiline_input():
    await parse_cmd([
        "--platform", "bili", "--type", "creator", "--creator_id",
        " 123\r\n456,789\n ",
    ])
    assert config.BILI_CREATOR_ID_LIST == ["123", "456", "789"]
