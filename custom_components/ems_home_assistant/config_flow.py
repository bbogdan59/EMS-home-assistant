"""Pairing, explicit local allowlist, review and end-to-end connection test."""

from copy import deepcopy
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    BridgeClient,
    BridgeError,
    CannotConnect,
    InvalidAuth,
    InvalidPairing,
    normalize_url,
)
from .const import DOMAIN, KINDS
from .mapping import collect_samples, create_mapping


def error_key(exc):
    if isinstance(exc, CannotConnect):
        return "cannot_connect"
    if isinstance(exc, (InvalidAuth, InvalidPairing)):
        return "invalid_auth"
    return "invalid_response"


class MappingSteps:
    """Common mapping UI for setup and options."""

    async def async_step_entity(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                mapping = create_mapping(self.hass, user_input)
                if any(m["entity_id"] == mapping["entity_id"] for m in self._config["mappings"]):
                    raise ValueError("duplicate_entity")
                if mapping["kind"] == "occupancy" and any(
                    m["kind"] == "occupancy" for m in self._config["mappings"]
                ):
                    raise ValueError("aggregate_only")
                self._config["mappings"].append(mapping)
                if not user_input["add_another"] or len(self._config["mappings"]) >= 20:
                    return await self.async_step_review()
            except ValueError as exc:
                errors["base"] = str(exc)
        registry = er.async_get(self.hass)
        selected = {m["entity_id"] for m in self._config["mappings"]}
        options = []
        for state in self.hass.states.async_all(("sensor", "binary_sensor", "input_number")):
            if state.entity_id in selected:
                continue
            entry = registry.async_get(state.entity_id)
            label = f"{state.entity_id} · {state.attributes.get('unit_of_measurement', 'state')} · {entry.platform if entry else 'local'} · {state.last_updated.isoformat()}"
            options.append({"value": state.entity_id, "label": label})
        options.sort(key=lambda item: item["value"])
        if not options:
            if self._config["mappings"]:
                return await self.async_step_review()
            return self.async_abort(reason="no_entities")
        return self.async_show_form(
            step_id="entity",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("entity_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required("kind", default="power"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=list(KINDS), translation_key="kind")
                    ),
                    vol.Required("max_age_seconds", default=180): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=3600)
                    ),
                    vol.Required("source_validated", default=False): bool,
                    vol.Required("simulated", default=False): bool,
                    vol.Required("add_another", default=False): bool,
                }
            ),
        )

    async def async_step_review(self, user_input=None):
        errors = {}
        if user_input is not None:
            if not user_input["consent"]:
                errors["base"] = "consent_required"
            elif (
                any(m["kind"] == "occupancy" for m in self._config["mappings"])
                and not user_input["occupancy_consent"]
            ):
                errors["base"] = "occupancy_consent_required"
            else:
                self._config.update(
                    {k: user_input[k] for k in ("occupancy_consent", "insights_consent")}
                )
                return await self.async_step_test()
        summary = "\n".join(
            f"- {m['entity_id']} → {m['kind']} ({m['unit']}, {m['quality']}, {m['max_age_seconds']} s)"
            for m in self._config["mappings"]
        )
        return self.async_show_form(
            step_id="review",
            errors=errors,
            description_placeholders={"mappings": summary},
            data_schema=vol.Schema(
                {
                    vol.Required("consent", default=False): bool,
                    vol.Required("occupancy_consent", default=False): bool,
                    vol.Required("insights_consent", default=False): bool,
                }
            ),
        )

    async def async_step_test(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._prepare_sync()
                if not getattr(self, "_configured", False):
                    self._config["mapping_version"] = await self._client.configure(self._config)
                    self._configured = True
                samples, _ = collect_samples(self.hass, self._config["mappings"], {})
                await self._client.send(self._config["mapping_version"], samples)
                return await self._finish()
            except BridgeError as exc:
                errors["base"] = error_key(exc)
        return self.async_show_form(step_id="test", data_schema=vol.Schema({}), errors=errors)

    async def _prepare_sync(self):
        """Setup has no previous stream to stop."""


class EMSConfigFlow(MappingSteps, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input["url"])
                self._client = BridgeClient(async_get_clientsession(self.hass), url)
                instance_id = str(uuid4())
                paired = await self._client.redeem(
                    user_input["code"], instance_id, self.hass.config.location_name[:80]
                )
                self._config = {
                    "url": url,
                    "token": paired["token"],
                    "station_id": paired["station_id"],
                    "station_name": paired["station_name"],
                    "instance_id": instance_id,
                    "mapping_version": paired["mapping_version"],
                    "mappings": [],
                    "occupancy_consent": False,
                    "insights_consent": False,
                }
                if self.source == config_entries.SOURCE_REAUTH:
                    old = self._get_reauth_entry()
                    if (old.data["url"], old.data["station_id"]) != (url, paired["station_id"]):
                        await self._client.disconnect()
                        return self.async_abort(reason="wrong_station")
                await self.async_set_unique_id(url + "|" + paired["station_id"])
                if self.source != config_entries.SOURCE_REAUTH:
                    self._abort_if_unique_id_configured()
                return await self.async_step_confirm()
            except ValueError:
                errors["base"] = "invalid_url"
            except BridgeError as exc:
                errors["base"] = error_key(exc)
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("url"): str,
                    vol.Required("code"): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            return await self.async_step_entity()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "station": self._config["station_name"],
                "station_id": self._config["station_id"],
                "instance": self.hass.config.location_name,
            },
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_user()

    async def _finish(self):
        if self.source == config_entries.SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=self._config)
        return self.async_create_entry(title=self._config["station_name"], data=self._config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EMSOptionsFlow()


class EMSOptionsFlow(MappingSteps, config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        self._client = BridgeClient(
            async_get_clientsession(self.hass),
            self.config_entry.data["url"],
            self.config_entry.data["token"],
        )
        return self.async_show_menu(step_id="init", menu_options=["entity", "disconnect"])

    async def async_step_entity(self, user_input=None):
        if not hasattr(self, "_config"):
            self._config = deepcopy(dict(self.config_entry.data))
            self._config["mappings"] = []
        return await super().async_step_entity(user_input)

    async def _finish(self):
        self._config["disconnected"] = False
        self.hass.config_entries.async_update_entry(self.config_entry, data=self._config)
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_create_entry(title="", data={})

    async def _prepare_sync(self):
        # Stop the old allowlist before saving a new one, including across restarts.
        runtime = getattr(self.config_entry, "runtime_data", None)
        if runtime:
            runtime.stopped = True
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, "disconnected": True}
        )

    async def async_step_disconnect(self, user_input=None):
        errors = {}
        if user_input is not None:
            runtime = getattr(self.config_entry, "runtime_data", None)
            if runtime:
                runtime.stopped = True
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, "disconnected": True}
            )
            try:
                await self._client.disconnect()
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, "token": "", "disconnected": True},
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            except BridgeError as exc:
                errors["base"] = error_key(exc)
        return self.async_show_form(step_id="disconnect", errors=errors, data_schema=vol.Schema({}))
