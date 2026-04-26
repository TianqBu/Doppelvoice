"""设备去重 (list_unique_devices) 单元测试 —— mock sounddevice。"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from doppelvoice.audio import devices


def _fake_query_devices():
    """模拟 sd.query_devices() 返回的 dict 列表。

    构造场景：
    - 一颗 ROG EYE S 摄像头麦在 4 个 host API 各注册一份（典型重复）
    - 一颗 CABLE Output 在 MME 是 31 字符截断版（典型 MME 截断）
    - 仅输出的设备：CABLE Input
    """
    return [
        # idx 0: MME 31字符截断 → 应被合并到 idx 1
        {"name": "CABLE Output (VB-Audio Virtual ", "max_input_channels": 1,
         "max_output_channels": 0, "default_samplerate": 44100.0, "hostapi": 0},
        # idx 1: DirectSound 完整名（应该是合并后的代表）
        {"name": "CABLE Output (VB-Audio Virtual Cable)", "max_input_channels": 1,
         "max_output_channels": 0, "default_samplerate": 44100.0, "hostapi": 1},
        # idx 2: WASAPI 同名
        {"name": "CABLE Output (VB-Audio Virtual Cable)", "max_input_channels": 1,
         "max_output_channels": 0, "default_samplerate": 44100.0, "hostapi": 2},
        # idx 3: ROG EYE S MME
        {"name": "麦克风 (ROG EYE S)", "max_input_channels": 1,
         "max_output_channels": 0, "default_samplerate": 44100.0, "hostapi": 0},
        # idx 4: ROG EYE S DirectSound
        {"name": "麦克风 (ROG EYE S)", "max_input_channels": 1,
         "max_output_channels": 0, "default_samplerate": 44100.0, "hostapi": 1},
        # idx 5: 输出设备 CABLE Input WASAPI
        {"name": "CABLE Input (VB-Audio Virtual Cable)", "max_input_channels": 0,
         "max_output_channels": 2, "default_samplerate": 48000.0, "hostapi": 2},
        # idx 6: 输出设备 CABLE Input MME 长度足够不需要截断
        {"name": "CABLE Input (VB-Audio Virtual Cable)", "max_input_channels": 0,
         "max_output_channels": 2, "default_samplerate": 48000.0, "hostapi": 0},
    ]


def _fake_query_hostapis():
    return [
        {"name": "MME"},
        {"name": "Windows DirectSound"},
        {"name": "Windows WASAPI"},
        {"name": "Windows WDM-KS"},
    ]


@pytest.fixture
def mock_sd():
    with patch.object(devices.sd, "query_devices", side_effect=_fake_query_devices), \
         patch.object(devices.sd, "query_hostapis", side_effect=_fake_query_hostapis):
        yield


def test_input_dedupes_by_name(mock_sd):
    """ROG EYE S 在 MME+DS 各一份，去重后只剩 1 条。"""
    out = devices.list_unique_devices("input")
    rog = [d for d in out if "ROG EYE S" in d.name]
    assert len(rog) == 1
    assert "MME" in rog[0].all_hostapis
    assert "Windows DirectSound" in rog[0].all_hostapis


def test_input_priority_picks_mme(mock_sd):
    """输入：MME 优先级 0 → ROG EYE S 应选 MME。"""
    out = devices.list_unique_devices("input")
    rog = next(d for d in out if "ROG EYE S" in d.name)
    assert rog.chosen_hostapi == "MME"


def test_mme_truncation_merged(mock_sd):
    """MME 31 字符截断的 'CABLE Output (VB-Audio Virtual ' 应合并到长名条目。"""
    out = devices.list_unique_devices("input")
    cable = [d for d in out if "CABLE Output" in d.name]
    assert len(cable) == 1, f"expected 1 CABLE Output, got {len(cable)}: {[d.name for d in cable]}"
    # 选中的应是长名条目（短名是 MME 的截断版）
    assert cable[0].name == "CABLE Output (VB-Audio Virtual Cable)"


def test_output_priority_picks_wasapi(mock_sd):
    """输出：WASAPI 优先级 0 → CABLE Input 应选 WASAPI。"""
    out = devices.list_unique_devices("output")
    cable = [d for d in out if "CABLE Input" in d.name]
    assert len(cable) == 1
    assert cable[0].chosen_hostapi == "Windows WASAPI"


def test_input_excludes_pure_output_devices(mock_sd):
    """list_unique_devices('input') 不应返回纯输出设备。"""
    out = devices.list_unique_devices("input")
    assert not any("CABLE Input " in d.name for d in out)


def test_output_excludes_pure_input_devices(mock_sd):
    """list_unique_devices('output') 不应返回纯输入设备。"""
    out = devices.list_unique_devices("output")
    assert not any("ROG EYE S" in d.name for d in out)
