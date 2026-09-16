import unittest
from unittest.mock import call, patch

from game_language import catalog_locale, normalize_game_lang, ocr_languages
import tarkov_api
import tarkov_json_fallback
from tarkov_api import _canon, _is_junk_ocr


class GameLanguageTests(unittest.TestCase):
    def test_zh_is_accepted(self) -> None:
        self.assertEqual(normalize_game_lang("zh"), "zh")

    def test_zh_uses_simplified_chinese_easyocr(self) -> None:
        self.assertEqual(ocr_languages("zh"), ("ch_sim", "en"))

    def test_en_reuses_the_warmed_ko_en_reader(self) -> None:
        self.assertEqual(ocr_languages("en"), ("ko", "en"))

    def test_zh_catalog_locale_stays_zh(self) -> None:
        self.assertEqual(catalog_locale("zh"), "zh")
        self.assertNotIn("ch_sim", catalog_locale("zh"))

    def test_short_chinese_names_are_not_junk(self) -> None:
        self.assertFalse(_is_junk_ocr("枪"))
        self.assertFalse(_is_junk_ocr("钥匙"))
        self.assertTrue(_is_junk_ocr("."))

    def test_nfkc_normalizes_full_width_text_before_matching(self) -> None:
        self.assertEqual(_canon("ＡＫ－７４"), "ak-74")
        self.assertTrue(_is_junk_ocr("１２３"))


class JsonCatalogLocalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = {
            "regular/items": {
                "data": {
                    "items": {
                        "main": {
                            "id": "main",
                            "name": "Item.Name",
                            "shortName": "Item.Short",
                            "types": [],
                            "properties": {},
                            "containsItems": [{"item": "inner", "count": 1}],
                            "sellToTrader": [{"trader": "trader1", "priceRUB": 100}],
                        },
                        "inner": {
                            "id": "inner",
                            "name": "Inner.Name",
                            "shortName": "Inner.Short",
                            "types": [],
                            "properties": {},
                        },
                        "english-only": {
                            "id": "english-only",
                            "name": "EnglishOnly.Name",
                            "shortName": "EnglishOnly.Short",
                            "types": [],
                            "properties": {},
                        },
                    }
                }
            },
            "regular/traders": {"data": {"trader1": {"name": "Trader.Name"}}},
            "regular/tasks": {
                "data": {
                    "tasks": {
                        "task1": {
                            "name": "Task.Name",
                            "trader": "trader1",
                            "objectives": [{"items": ["main"], "count": 1}],
                        }
                    }
                }
            },
            "regular/barters": {
                "data": [{
                    "trader": "trader1",
                    "minTraderLevel": 1,
                    "taskUnlock": "task1",
                    "offeredItem": {"item": "main", "count": 1},
                    "requiredItems": [{"item": "inner", "count": 2}],
                }]
            },
            "regular/hideout": {
                "data": {
                    "station1": {
                        "name": "Station.Name",
                        "levels": [{
                            "level": 1,
                            "itemRequirements": [{
                                "item": "inner",
                                "count": 1,
                                "attributes": {},
                            }],
                        }],
                    }
                }
            },
            "regular/crafts": {
                "data": [{
                    "station": "station1",
                    "level": 1,
                    "duration": 10,
                    "productItem": {"item": "main"},
                    "requiredItems": [{"item": "inner", "count": 1}],
                }]
            },
        }
        self.locales = {
            "regular/items_zh": {
                "Item.Name": "中文物品",
                "Inner.Name": "中文材料",
                "Inner.Short": "中文材料短名",
                "EnglishOnly.Short": "中文短名",
            },
            "regular/items_en": {
                "Item.Name": "English Item",
                "Item.Short": "English Short",
                "Inner.Name": "English Material",
                "Inner.Short": "English Material Short",
                "EnglishOnly.Name": "English Only",
                "EnglishOnly.Short": "English Only Short",
            },
            "regular/tasks_zh": {},
            "regular/tasks_en": {"Task.Name": "English Task"},
            "regular/traders_zh": {},
            "regular/traders_en": {"Trader.Name": "English Trader"},
            "regular/hideout_zh": {},
            "regular/hideout_en": {"Station.Name": "English Station"},
        }

    def test_zh_json_fields_and_enrichment_fallback_individually(self) -> None:
        def raw_get(path: str) -> dict:
            return self.raw.get(path, {"data": {}})

        def locale_get(path: str) -> dict:
            return self.locales.get(path, {})

        with patch.object(tarkov_json_fallback, "_get_cached", side_effect=raw_get), \
             patch.object(tarkov_json_fallback, "_get_locale", side_effect=locale_get):
            items, _hideout_index, stations = tarkov_json_fallback.fetch_catalog(
                "zh", "regular"
            )

        main = next(item for item in items if item["id"] == "main")
        english_only = next(item for item in items if item["id"] == "english-only")
        self.assertEqual(main["name"], "中文物品")
        self.assertEqual(main["shortName"], "English Short")
        self.assertEqual(english_only["name"], "English Only")
        self.assertEqual(english_only["shortName"], "中文短名")
        self.assertEqual(stations[0]["name"], "English Station")
        self.assertEqual(main["usedInTasks"][0]["name"], "English Task")
        self.assertEqual(main["bartersFor"][0]["trader"]["name"], "English Trader")
        self.assertEqual(main["bartersFor"][0]["taskUnlock"]["name"], "English Task")
        self.assertEqual(main["bartersFor"][0]["requiredItems"][0]["item"]["name"], "中文材料")
        self.assertEqual(main["craftsFor"][0]["station"]["name"], "English Station")
        self.assertEqual(main["craftsFor"][0]["requiredItems"][0]["item"]["name"], "中文材料")


class GraphQLLocalizationTests(unittest.TestCase):
    def test_graphql_zh_merges_only_missing_fields(self) -> None:
        primary = [{
            "id": "main",
            "name": "中文物品",
            "shortName": "",
            "bartersFor": [{
                "trader": {"id": "trader1", "name": ""},
                "taskUnlock": {"id": "task1", "name": None},
                "requiredItems": [{
                    "item": {"id": "inner", "name": "中文材料", "shortName": ""}
                }],
            }],
            "usedInTasks": [{
                "id": "task1",
                "name": "",
                "trader": {"id": "trader1", "name": ""},
            }],
            "craftsFor": [{
                "station": {"id": "station1", "name": ""},
                "requiredItems": [{
                    "item": {"id": "inner", "name": "中文材料", "shortName": ""}
                }],
            }],
        }]
        english = [{
            "id": "main",
            "name": "English Item",
            "shortName": "English Short",
            "bartersFor": [{
                "trader": {"id": "trader1", "name": "English Trader"},
                "taskUnlock": {"id": "task1", "name": "English Task"},
                "requiredItems": [{
                    "item": {"id": "inner", "name": "English Material", "shortName": "English Material Short"}
                }],
            }],
            "usedInTasks": [{
                "id": "task1",
                "name": "English Task",
                "trader": {"id": "trader1", "name": "English Trader"},
            }],
            "craftsFor": [{
                "station": {"id": "station1", "name": "English Station"},
                "requiredItems": [{
                    "item": {"id": "inner", "name": "English Material", "shortName": "English Material Short"}
                }],
            }],
        }]
        with patch.object(tarkov_api, "_fetch_graphql_catalog", return_value=english) as fetch:
            merged = tarkov_api._localized_graphql_catalog(primary, "zh", "regular")

        fetch.assert_called_once_with("en", "regular", use_cache=True)
        self.assertEqual(merged[0]["name"], "中文物品")
        self.assertEqual(merged[0]["shortName"], "English Short")
        self.assertEqual(merged[0]["bartersFor"][0]["trader"]["name"], "English Trader")
        self.assertEqual(merged[0]["bartersFor"][0]["taskUnlock"]["name"], "English Task")
        self.assertEqual(
            merged[0]["bartersFor"][0]["requiredItems"][0]["item"]["name"],
            "中文材料",
        )
        self.assertEqual(
            merged[0]["bartersFor"][0]["requiredItems"][0]["item"]["shortName"],
            "English Material Short",
        )
        self.assertEqual(merged[0]["usedInTasks"][0]["name"], "English Task")
        self.assertEqual(merged[0]["usedInTasks"][0]["trader"]["name"], "English Trader")
        self.assertEqual(merged[0]["craftsFor"][0]["station"]["name"], "English Station")
        self.assertEqual(
            merged[0]["craftsFor"][0]["requiredItems"][0]["item"]["name"],
            "中文材料",
        )

    def test_graphql_catalog_requests_zh_locale(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"data": {"items": [{"id": "item1", "name": "中文", "shortName": "短"}]}}

        with patch.object(tarkov_api.requests, "post", return_value=Response()) as post:
            try:
                tarkov_api._fetch_graphql_catalog("zh", "regular")
                payload = post.call_args.kwargs["json"]
                self.assertEqual(payload["variables"]["lang"], "zh")
            finally:
                tarkov_api._graphql_catalog_cache.pop(("zh", "regular"), None)

    def test_zh_graphql_failure_uses_zh_json_fallback(self) -> None:
        fallback_item = {
            "id": "zh-item",
            "name": "中文物品",
            "shortName": "中文短名",
            "types": [],
            "properties": {},
        }
        with patch.object(tarkov_api.requests, "post", side_effect=RuntimeError("offline")), \
             patch.object(
                 tarkov_json_fallback,
                 "fetch_catalog",
                 return_value=([fallback_item], {}, []),
             ) as fetch:
            try:
                tarkov_api._refresh_one("zh", "regular")
                fetch.assert_called_once_with("zh", "regular")
                self.assertIn(("zh", "regular"), tarkov_api._price_cache)
                self.assertNotIn(("en", "regular"), tarkov_api._price_cache)
            finally:
                for cache in (
                    tarkov_api._price_cache,
                    tarkov_api._canon_cache,
                    tarkov_api._price_cache_ts,
                ):
                    cache.pop(("zh", "regular"), None)
                tarkov_api._names_cache.pop("zh", None)

    def test_graphql_zh_hideout_station_uses_english_only_when_missing(self) -> None:
        class Response:
            def __init__(self, stations: list[dict]) -> None:
                self.stations = stations

            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"data": {"hideoutStations": self.stations}}

        responses = [
            Response([{"id": "station1", "name": "", "levels": []}]),
            Response([{"id": "station1", "name": "English Station", "levels": []}]),
        ]
        with patch.object(tarkov_api.requests, "post", side_effect=responses):
            _index, stations = tarkov_api._fetch_hideout_index("zh")

        self.assertEqual(stations[0]["name"], "English Station")

    def test_graphql_zh_ammo_uses_english_only_for_missing_names(self) -> None:
        rows = {
            "zh": [{
                "item": {"id": "ammo1", "name": "中文弹药", "shortName": ""},
                "caliber": "Caliber545x39",
                "penetrationPower": 1,
            }],
            "en": [{
                "item": {"id": "ammo1", "name": "English Ammo", "shortName": "EA"},
                "caliber": "Caliber545x39",
                "penetrationPower": 1,
            }],
        }
        with patch.object(
            tarkov_api,
            "_fetch_graphql_ammo",
            side_effect=lambda lang, use_cache=False: rows[lang],
        ) as fetch:
            data = tarkov_api._fetch_ammo("zh")

        fetch.assert_has_calls([
            call("zh"),
            call("en", use_cache=True),
        ])
        self.assertEqual(data["calibers"]["Caliber545x39"]["rounds"][0]["name"], "中文弹药")
        self.assertEqual(data["calibers"]["Caliber545x39"]["rounds"][0]["short_name"], "EA")

    def test_language_catalog_caches_are_independent(self) -> None:
        with patch.dict(
            tarkov_api._price_cache,
            {
                ("en", "regular"): {"English": {}},
                ("zh", "regular"): {"中文": {}},
            },
            clear=True,
        ):
            self.assertEqual(tarkov_api._price_cache[("en", "regular")], {"English": {}})
            self.assertEqual(tarkov_api._price_cache[("zh", "regular")], {"中文": {}})


if __name__ == "__main__":
    unittest.main()
