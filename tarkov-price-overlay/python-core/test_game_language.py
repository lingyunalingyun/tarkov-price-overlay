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

    def test_reordered_barters_use_item_signature_not_position(self) -> None:
        zh = [
            {
                "trader": {"id": "trader1", "name": ""},
                "level": 2,
                "requiredItems": [{"count": 1, "item": {"id": "req-a", "name": "甲", "shortName": ""}}],
            },
            {
                "trader": {"id": "trader1", "name": ""},
                "level": 2,
                "requiredItems": [{"count": 2, "item": {"id": "req-b", "name": "乙", "shortName": ""}}],
            },
        ]
        en = [
            {
                "trader": {"id": "trader1", "name": "Trader"},
                "level": 2,
                "requiredItems": [{"count": 2, "item": {"id": "req-b", "name": "English B", "shortName": "English B short"}}],
            },
            {
                "trader": {"id": "trader1", "name": "Trader"},
                "level": 2,
                "requiredItems": [{"count": 1, "item": {"id": "req-a", "name": "English A", "shortName": "English A short"}}],
            },
        ]
        merged = tarkov_api._merge_barter_rows(zh, en)
        self.assertEqual(merged[0]["requiredItems"][0]["item"]["shortName"], "English A short")
        self.assertEqual(merged[1]["requiredItems"][0]["item"]["shortName"], "English B short")

    def test_reordered_crafts_use_station_and_material_signature(self) -> None:
        zh = [
            {
                "station": {"id": "station1", "name": ""},
                "level": 1,
                "duration": 60,
                "requiredItems": [{"count": 1, "item": {"id": "req-a", "name": "甲", "shortName": ""}}],
            },
            {
                "station": {"id": "station1", "name": ""},
                "level": 1,
                "duration": 60,
                "requiredItems": [{"count": 2, "item": {"id": "req-b", "name": "乙", "shortName": ""}}],
            },
        ]
        en = [
            {
                "station": {"id": "station1", "name": "Workbench"},
                "level": 1,
                "duration": 60,
                "requiredItems": [{"count": 2, "item": {"id": "req-b", "name": "English B", "shortName": "English B short"}}],
            },
            {
                "station": {"id": "station1", "name": "Workbench"},
                "level": 1,
                "duration": 60,
                "requiredItems": [{"count": 1, "item": {"id": "req-a", "name": "English A", "shortName": "English A short"}}],
            },
        ]
        merged = tarkov_api._merge_craft_rows(zh, en)
        self.assertEqual(merged[0]["requiredItems"][0]["item"]["shortName"], "English A short")
        self.assertEqual(merged[1]["requiredItems"][0]["item"]["shortName"], "English B short")

    def test_reordered_vendor_offers_use_vendor_and_price(self) -> None:
        zh = {
            "id": "item1",
            "name": "中文物品",
            "sellFor": [
                {"priceRUB": 100, "vendor": {"id": "trader1", "name": ""}},
                {"priceRUB": 200, "vendor": {"id": "trader1", "name": ""}},
            ],
        }
        en = {
            "id": "item1",
            "name": "English Item",
            "sellFor": [
                {"priceRUB": 200, "vendor": {"id": "trader1", "name": "High offer"}},
                {"priceRUB": 100, "vendor": {"id": "trader1", "name": "Low offer"}},
            ],
        }
        merged = tarkov_api._merge_graphql_item(zh, en)
        offers = {offer["priceRUB"]: offer["vendor"]["name"] for offer in merged["sellFor"]}
        self.assertEqual(offers, {100: "Low offer", 200: "High offer"})

    def test_item_queries_request_nested_stable_ids(self) -> None:
        for query in (tarkov_api._QUERY_BY_NAME, tarkov_api._QUERY_ALL_PRICED):
            self.assertIn("vendor { id name }", query)
            self.assertIn("trader { id name }", query)
            self.assertIn("item { id name shortName }", query)

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
             ) as fetch, \
             patch.object(
                 tarkov_json_fallback,
                 "fetch_item_names",
                 return_value=[],
             ) as fetch_names:
            try:
                tarkov_api._refresh_one("zh", "regular")
                fetch.assert_called_once_with("zh", "regular")
                fetch_names.assert_called_once_with("en", "regular")
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


class ChineseMatchingAliasTests(unittest.TestCase):
    def tearDown(self) -> None:
        for cache in (
            tarkov_api._price_cache,
            tarkov_api._canon_cache,
            tarkov_api._price_cache_ts,
            tarkov_api._hideout_index_cache,
            tarkov_api._hideout_station_list_cache,
        ):
            cache.pop(("zh", "regular"), None)
        tarkov_api._names_cache.pop("zh", None)

    @staticmethod
    def _item(item_id: str, name: str, short_name: str, types=None) -> dict:
        return {
            "id": item_id,
            "name": name,
            "shortName": short_name,
            "types": types or [],
            "properties": {},
            "sellFor": [],
        }

    def _refresh_graphql(self, zh_items: list[dict], english_items: list[dict]) -> dict:
        def fetch(lang: str, game_mode: str, use_cache: bool = False) -> list[dict]:
            return zh_items if lang == "zh" else english_items

        with patch.object(tarkov_api, "_fetch_graphql_catalog", side_effect=fetch), \
             patch.object(tarkov_api, "_fetch_hideout_index", return_value=({}, [])):
            tarkov_api._refresh_one("zh", "regular")
        return tarkov_api._price_cache[("zh", "regular")]

    def test_english_full_name_alias_returns_zh_entry(self) -> None:
        zh = [self._item("armor", "6B2防弹衣（Flora）", "6B2护甲", ["armor"])]
        en = [self._item("armor", "6B2 body armor (Flora)", "6B2 body armor", ["armor"])]

        cache = self._refresh_graphql(zh, en)

        self.assertEqual(cache["6B2 body armor (Flora)"]["name"], "6B2防弹衣（Flora）")
        self.assertIs(cache["6B2 body armor (Flora)"], cache["6B2防弹衣（Flora）"])

    def test_english_short_name_alias_returns_same_zh_entry(self) -> None:
        zh = [self._item("armor", "6B2防弹衣（Flora）", "6B2护甲", ["armor"])]
        en = [self._item("armor", "6B2 body armor (Flora)", "6B2 body armor", ["armor"])]

        cache = self._refresh_graphql(zh, en)

        self.assertEqual(cache["6B2 body armor"]["name"], "6B2防弹衣（Flora）")
        self.assertIs(cache["6B2 body armor"], cache["6B2防弹衣（Flora）"])

    def test_full_names_and_english_canonical_alias_share_entry(self) -> None:
        zh = [self._item("armor", "6B2防弹衣（Flora）", "6B2护甲", ["armor"])]
        en = [self._item("armor", "6B2 body armor (Flora)", "6B2 body armor", ["armor"])]

        cache = self._refresh_graphql(zh, en)

        result = tarkov_api._cache_lookup("GBZ body armor (Flora)", "zh", "regular", None)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "6B2防弹衣（Flora）")
        self.assertIs(cache["6B2 body armor (Flora)"], cache["6B2防弹衣（Flora）"])

    def test_json_fallback_builds_english_aliases_by_stable_id(self) -> None:
        zh = [self._item("armor", "6B2防弹衣（Flora）", "6B2护甲", ["armor"])]
        en = [self._item("armor", "6B2 body armor (Flora)", "6B2 body armor", ["armor"])]
        with patch.object(tarkov_api, "_fetch_graphql_catalog", side_effect=RuntimeError("offline")), \
             patch.object(tarkov_json_fallback, "fetch_catalog", return_value=(zh, {}, [])), \
             patch.object(tarkov_json_fallback, "fetch_item_names", return_value=en):
            tarkov_api._refresh_one("zh", "regular")

        result = tarkov_api._cache_lookup("6B2 body armor (Flora)", "zh", "regular", None)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "6B2防弹衣（Flora）")

    def test_english_alias_does_not_replace_another_zh_full_name(self) -> None:
        zh = [
            self._item("first", "中文物品一", "短名一"),
            self._item("second", "中文物品二", "短名二"),
        ]
        en = [
            self._item("first", "中文物品二", "English One"),
            self._item("second", "English Two", "English Two Short"),
        ]

        cache = self._refresh_graphql(zh, en)

        self.assertEqual(cache["中文物品二"]["id"], "second")
        self.assertEqual(cache["English Two"]["id"], "second")


if __name__ == "__main__":
    unittest.main()
