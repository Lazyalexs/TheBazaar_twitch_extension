from companion.log_companion import BazaarLogState, TemplateInfo


def test_log_state_links_instances_to_exact_templates():
    templates = {
        "bf90b501-0d87-49ae-a82a-5941db70179c": TemplateInfo(
            template_id="bf90b501-0d87-49ae-a82a-5941db70179c",
            title="Weather Machine",
            size="Large",
            tier="gold",
            cooldown=7,
        ),
        "3132efea-ee79-4b99-b380-d0df3bf1df88": TemplateInfo(
            template_id="3132efea-ee79-4b99-b380-d0df3bf1df88",
            title="Cruise Ship",
            size="Large",
            tier="gold",
            cooldown=6,
        ),
    }
    state = BazaarLogState(templates)

    lines = [
        "[09:38:58.146] [BoardManager] Card Purchased: InstanceId: itm_NrptOas - TemplateIdbf90b501-0d87-49ae-a82a-5941db70179c - Target:PlayerSocket_0 - SectionPlayer",
        "[16:40:16.835] [BoardManager] Card Purchased: InstanceId: itm_aw8weKP - TemplateId3132efea-ee79-4b99-b380-d0df3bf1df88 - Target:PlayerStorageSocket_3 - SectionStorage",
        "[09:41:17.418] [GameSimHandler] Cards Spawned: [itm_NrptOas [Player] [Hand] [Socket_0] [Large] | [itm_aw8weKP [Player] [Hand] [Socket_6] [Large] |",
    ]
    for line in lines:
        state.apply_line(line)

    payload = state.payload("5.0.0")

    assert payload["board"][0]["id"] == "Weather Machine"
    assert payload["board"][0]["slot"] == 0
    assert payload["board"][0]["source"] == "game"
    assert payload["board"][0]["confidence"] == 1
    assert payload["board"][1]["id"] == "Cruise Ship"
    assert payload["board"][1]["slot"] == 6
