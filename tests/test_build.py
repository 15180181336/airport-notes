import copy
import importlib.util
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", ROOT / "tools/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))

    def test_directory_accepts_documented_without_personal_test(self):
        self.assertIs(builder.validate(self.data), self.data)
        self.assertFalse(self.data["providers"][0]["experiences"])

    def test_referral_fragment_is_preserved_and_disclosed(self):
        p = self.data["providers"][0]
        output = builder.provider_page(p)
        self.assertIn("(https://www.xueshan.shop/#/register?code=5Rl9uaQh)", output)
        self.assertIn("维护者可能获得佣金", output)

    def test_unconfirmed_referral_not_promoted(self):
        p = copy.deepcopy(self.data["providers"][1])
        p["referral_url"] = "https://example.org/register?code=unconfirmed"
        p["referral_confirmed"] = False
        self.assertNotIn(p["referral_url"], builder.provider_page(p))

    def test_primary_entry_uses_invitation_not_bare_official_url(self):
        p = self.data["providers"][0]
        self.assertIn(p["referral_url"], builder.entry_link(p))
        self.assertNotEqual(builder.entry_link(p), builder.link("网站入口", p["official_url"]))

    def test_missing_invitation_does_not_fall_back_to_official_url(self):
        p = next(p for p in self.data["providers"] if p["id"] == "bianjiecloud")
        self.assertTrue(p["official_url"])
        self.assertEqual(builder.entry_link(p), "邀请链接待补")

    def test_home_directory_and_offer_rows_preserve_invitation(self):
        content = builder.readme(self.data)
        provider = self.data["providers"][0]
        rows = [row for row in content.splitlines() if row.startswith("| [雪山")]
        self.assertEqual(len(rows), 1 + len(provider["offers"]))
        for row in rows:
            self.assertIn("](" + provider["referral_url"] + ")", row)
            self.assertNotIn("](" + provider["official_url"] + ")", row)

    def test_sufe_registration_uses_owner_screenshot_code(self):
        provider = next(p for p in self.data["providers"] if p["id"] == "sufe")
        self.assertEqual(provider["referral_url"], "https://sufe.us/register?code=UqMAwue5")
        self.assertIn(provider["referral_url"], builder.entry_link(provider))

    def test_paused_provider_has_no_primary_registration_link(self):
        provider = copy.deepcopy(self.data["providers"][0])
        provider["status"] = "paused"
        self.assertEqual(builder.entry_link(provider), "入口已暂停")

    def test_paused_referral_not_linked(self):
        p = copy.deepcopy(self.data["providers"][0])
        p["status"] = "paused"
        self.assertNotIn("](" + p["referral_url"] + ")", builder.provider_page(p))

    def test_unconfirmed_referral_also_disabled_in_sources(self):
        p = copy.deepcopy(self.data["providers"][0])
        p["referral_confirmed"] = False
        self.assertNotIn("](" + p["referral_url"] + ")", builder.provider_page(p))

    def test_missing_source_rejected(self):
        self.data["providers"][0]["facts"][0]["source"] = "missing"
        with self.assertRaisesRegex(ValueError, "不存在的来源"):
            builder.validate(self.data)

    def test_duplicate_provider_rejected(self):
        self.data["providers"].append(copy.deepcopy(self.data["providers"][0]))
        with self.assertRaisesRegex(ValueError, "重复"):
            builder.validate(self.data)

    def test_public_schema_rejects_account_password(self):
        self.data["providers"][0]["password"] = "DO-NOT-PUBLISH"
        with self.assertRaisesRegex(ValueError, "字段不匹配"):
            builder.validate(self.data)

    def test_unsafe_url_rejected(self):
        self.data["providers"][0]["official_url"] = "javascript:alert(1)"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            builder.validate(self.data)

    def test_evidence_cannot_leave_public_repository(self):
        with self.assertRaises(ValueError):
            builder.local_file(ROOT, "evidence/../../private.txt")

    def test_export_is_explicit_not_recursive(self):
        files = builder.package_files(self.data)
        self.assertNotIn("运营手册.md", files)
        self.assertNotIn(".env", files)
        self.assertTrue(all(".." not in Path(f).parts for f in files))

    def test_markup_in_source_text_is_escaped(self):
        self.assertEqual(builder.md("<script>"), "&lt;script&gt;")
        self.assertIn("\\|", builder.md("a|b"))

    def test_cover_is_valid_svg(self):
        self.assertEqual(ET.parse(ROOT / "assets/cover.svg").getroot().tag,
                         "{http://www.w3.org/2000/svg}svg")

    def test_yearly_offer_shows_full_upfront_payment(self):
        provider = next(p for p in self.data["providers"] if p["id"] == "bianjiecloud")
        yearly = next(o for o in provider["offers"] if o["billing"] == "yearly")
        self.assertEqual(builder.offer_price(yearly), "¥189 / 年付")
        self.assertEqual(builder.offer_quota(yearly), "100 GB（每月）")
        self.assertIn("厂商说明", builder.offer_source(provider, yearly))

    def test_third_party_price_keeps_source_label(self):
        provider = next(p for p in self.data["providers"] if p["id"] == "tag")
        self.assertIn("第三方公开资料", builder.offer_source(provider, provider["offers"][0]))
        self.assertIn("周期待核实", builder.offer_quota(provider["offers"][0]))

    def test_offer_must_have_valid_source(self):
        self.data["providers"][0]["offers"][0]["source"] = "nonexistent"
        with self.assertRaisesRegex(ValueError, "不存在的来源"):
            builder.validate(self.data)

    def test_nan_price_rejected(self):
        self.data["providers"][0]["offers"][0]["total_cny"] = float("nan")
        with self.assertRaisesRegex(ValueError, "正数或 null"):
            builder.validate(self.data)

    def test_no_quota_does_not_claim_unlimited(self):
        provider = next(p for p in self.data["providers"] if p["id"] == "guodong")
        self.assertEqual(builder.offer_quota(provider["offers"][0]), "流量额度待核实")


if __name__ == "__main__":
    unittest.main()
