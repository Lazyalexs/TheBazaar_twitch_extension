from companion.log_stats import summarize_log_text


def test_summarize_log_text_counts_streamer_events():
    stats = summarize_log_text(
        "\n".join(
            [
                "[16:40:15.181] [BoardManager] Card Purchased: InstanceId: itm_NrptOas - TemplateIdbf90b501-0d87-49ae-a82a-5941db70179c - Target:PlayerStorageSocket_0 - SectionStorage",
                "[16:40:16.835] [BoardManager] Card Purchased: InstanceId: enc_x - TemplateId3132efea-ee79-4b99-b380-d0df3bf1df88 - Target:OpponentSocket_5 - SectionOpponent",
                "[16:40:08.944] [BoardManager] Sold Card itm_BkdykaQ for 3 gold.",
                "[16:40:55.081] [AppState] State changed from [ChoiceState] to [PVPCombatState]",
                "[16:41:26.950] [CombatSimHandler] Combat simulation completed in 20,5607263s",
                "[16:41:34.877] [AppState] State changed from [PVPCombatState] to [ReplayState]",
                "[16:43:28.044] [GameSimHandler] Cards Dealt: [enc_3ECUxAb [Medium] |",
            ]
        )
    )

    assert stats.phase == "shopping"
    assert stats.purchases == 1
    assert stats.sales == 1
    assert stats.sold_gold == 3
    assert stats.combats == 1
    assert stats.pvp_combats == 1
    assert stats.combat_completions == 1
    assert stats.cards_dealt_events == 1
