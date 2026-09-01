// Generated compact Opponent Intent runtime bundle.
// Contains aggregate coefficients/profile features only; no raw league history.
(() => {
  const deepFreeze = (value) => {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
    Object.freeze(value);
    Object.values(value).forEach(deepFreeze);
    return value;
  };
  window.OPPONENT_INTENT_PACKAGE = deepFreeze({
    "schemaVersion": "1.0.0",
    "packageId": "espn-opponent-intent-runtime-2026-08-31",
    "season": 2026,
    "leagueProfileId": "espn-keeper-10-ppr-2flex-2026",
    "leagueId": "167404",
    "metadata": {
      "status": "candidate",
      "modelVersion": "espn_opponent_intent_v1.1_candidate",
      "generatedAt": "2026-08-31T22:45:00Z",
      "effectiveAt": "2026-09-01T00:30:12Z",
      "sourceVersions": {
        "history": "ESPN League Draft Picks.xlsx; 2020-2025",
        "enrichment": "StepB Rounds 1-6; ESPN rank and ESPN ADP separate",
        "league": "espn_league_2026_v1_1_api_reconciled",
        "market": "espn_2026_frozen_20260901T003012Z_3379127ab1c0"
      },
      "market": {
        "snapshotId": "espn_2026_frozen_20260901T003012Z_3379127ab1c0",
        "captureTimestampUtc": "2026-09-01T00:30:12Z",
        "publicationCommit": "49951ca1d45b92a906f84366a02d40c8c2e07e12",
        "snapshotSha256": "e333dfbc3196351ea1b04f6fa8a5525db5903067f38318c8d2a725d6f75bc2a2",
        "schemaVersion": "espn-market-2026-v1.1",
        "status": "frozen",
        "canonicalSnapshotPath": "fantasy-draft/data/derived/espn_market/espn_2026_market_snapshot_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json",
        "canonicalManifestPath": "fantasy-draft/data/production/espn_2026_market_manifest_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json",
        "coverage": {
          "sourceRows": 500,
          "draftCommandIdentities": {
            "mapped": 199,
            "total": 200
          },
          "mappedWithEspnDefaultRank": {
            "count": 199,
            "total": 199
          },
          "mappedWithContinuousEspnAdp": {
            "count": 199,
            "total": 199
          },
          "keepersRepresented": {
            "count": 10,
            "total": 10
          },
          "unresolvedEspnTop160": 0,
          "duplicateInternalPlayerIds": 0,
          "duplicateEspnPlayerIds": 0,
          "draftCommandOnlyMisses": [
            {
              "playerId": 190,
              "reason": "outside ESPN payload",
              "blocking": false
            }
          ]
        },
        "fieldPolicy": {
          "espnDefaultRank": "distinct nullable ESPN PPR default-rank field",
          "espnAdp": "distinct nullable continuous ESPN ADP field",
          "ordinalAdpRankCreated": false,
          "rankAdpBlended": false
        }
      },
      "historicalCoverage": "2020-2025 history; held-out 2023-2025; Rounds 1-6",
      "calibratedRounds": [
        1,
        2,
        3,
        4,
        5,
        6
      ],
      "confidencePolicy": "MEDIUM only in validated Rounds 1-6; manager probability weight 0; fallback otherwise",
      "knownLimitations": [
        "Rounds 7-16 are contextual and unvalidated.",
        "Authenticated league-settings verification remains incomplete; the public market lock did not verify private scoring, roster or IR/Stash settings.",
        "Manager profiles remain explanatory and do not alter probabilities.",
        "Runtime Monte Carlo sampling adds finite-simulation noise, controlled by a fixed seed."
      ],
      "publicAssetPolicy": "Aggregate runtime features only; raw history and pick-level ledgers excluded."
    },
    "policy": {
      "positionManagerResidualWeight": 0,
      "playerManagerResidualWeight": 0,
      "promotionStatus": "REJECTED_GLOBAL_NO_ROBUST_HOLDOUT_GAIN",
      "rosterAndRoomContextEnabled": true,
      "profileEvidenceExplanationOnly": true,
      "tonyValuesAffectSelectionProbability": false,
      "tierLabelsAffectSelectionProbability": false
    },
    "positionModel": {
      "dynamicBase": {
        "features": [
          "room_log_prob",
          "roster_count",
          "open_mandatory",
          "flex_open_skill",
          "last_same",
          "recent_run_count",
          "best_board_log",
          "top12_share",
          "round_norm",
          "pos_QB",
          "pos_RB",
          "pos_WR",
          "pos_TE"
        ],
        "scaler_mean": [
          -1.7305664775007528,
          0.853448275862069,
          0.735632183908046,
          1.2327586206896552,
          0.20689655172413793,
          1.4094827586206897,
          -1.8619941438173457,
          0.22629310344827586,
          0.5723180076628352,
          0.25,
          0.25,
          0.25,
          0.25
        ],
        "scaler_scale": [
          0.9926382798763279,
          0.9862938029387683,
          0.5925256697469096,
          0.8769830594507597,
          0.4050806939472666,
          1.4524540340289958,
          1.0501331586573461,
          0.19228599167936217,
          0.2827354358985819,
          0.4330127018922193,
          0.4330127018922193,
          0.4330127018922193,
          0.4330127018922193
        ],
        "coef": [
          0.20768621433418455,
          -0.6285010589026621,
          0.10879017249496724,
          0.19290356090601224,
          0.05521023719323989,
          0.04164783944056855,
          1.68924917885518,
          0.308707428954202,
          0.6963904561552386,
          -0.3275903514182112,
          0.18965109643962746,
          0.4488716598994821,
          -0.31093240492090013
        ],
        "intercept": -2.1385288857020086
      },
      "roomBaselines": {
        "R1_3": {
          "QB": 0.03260869565217391,
          "RB": 0.3804347826086957,
          "WR": 0.5163043478260869,
          "TE": 0.07065217391304347
        },
        "R4_6": {
          "QB": 0.13372093023255813,
          "RB": 0.31976744186046513,
          "WR": 0.4476744186046512,
          "TE": 0.09883720930232558
        }
      }
    },
    "playerModel": {
      "rankWeight": 0.6,
      "adpWeight": 0.4,
      "boardDecayLambda": 0.35
    },
    "validation": {
      "position_room_baseline": {
        "n": 173,
        "log_loss": 1.150593191386496,
        "brier": 0.1581844837026222,
        "top1_accuracy": 0.5028901734104047,
        "top2_coverage": 0.8265895953757225
      },
      "position_needs": {
        "n": 173,
        "log_loss": 1.0625610588094025,
        "brier": 0.1486573517897769,
        "top1_accuracy": 0.5375722543352601,
        "top2_coverage": 0.8265895953757225
      },
      "position_runs_context": {
        "n": 173,
        "log_loss": 0.8796874836963756,
        "brier": 0.13050097707458627,
        "top1_accuracy": 0.5780346820809249,
        "top2_coverage": 0.884393063583815
      },
      "position_dynamic_base": {
        "n": 173,
        "log_loss": 0.8796874836963756,
        "brier": 0.1305009770745863,
        "top1_accuracy": 0.5780346820809249,
        "top2_coverage": 0.884393063583815
      },
      "position_manager_full": {
        "n": 173,
        "log_loss": 0.8823337715788623,
        "brier": 0.12968225712400624,
        "top1_accuracy": 0.6069364161849711,
        "top2_coverage": 0.861271676300578
      },
      "position_final_capped_overlay": {
        "n": 173,
        "log_loss": 0.8796874836963756,
        "brier": 0.1305009770745863,
        "top1_accuracy": 0.5780346820809249,
        "top2_coverage": 0.884393063583815
      },
      "player_market_only": {
        "n": 173,
        "log_loss": 2.090205724948546,
        "top1_accuracy": 0.3179190751445087,
        "top3_coverage": 0.630057803468208,
        "top5_coverage": 0.8265895953757225,
        "mean_actual_rank": 3.7514450867052025,
        "average_espn_board_distance": 3.2393063583815023,
        "conditional_log_loss": 1.2105182412521707
      },
      "player_profile_capped_overlay": {
        "n": 173,
        "log_loss": 2.090205724948546,
        "top1_accuracy": 0.3179190751445087,
        "top3_coverage": 0.630057803468208,
        "top5_coverage": 0.8265895953757225,
        "mean_actual_rank": 3.7514450867052025,
        "average_espn_board_distance": 3.2393063583815023,
        "conditional_log_loss": 1.2105182412521707
      }
    },
    "managers": [
      {
        "espnTeamId": 10,
        "draftSlot": 1,
        "manager": "Justin Gerkin",
        "teamName": "Team Pickle Tickle",
        "keeper": {
          "name": "Sam LaPorta",
          "position": "TE",
          "round": 6
        },
        "sampleSize": 36,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "STRONG_BOARD_FOLLOWER",
        "alignment": "FIXED_RANK_LEAN_STRONG",
        "boardModeProbability": 0.865864,
        "convictionModeProbability": 0.134136,
        "espnRankWeight": 0.594461,
        "espnAdpWeight": 0.405539,
        "round1To3PositionProfile": {
          "RB": 0.45026,
          "WR": 0.485096,
          "QB": 0.01667,
          "TE": 0.047974
        },
        "round4To6PositionProfile": {
          "RB": 0.340395,
          "WR": 0.459377,
          "QB": 0.105335,
          "TE": 0.094893
        },
        "ordinaryTeNeedMultiplier": 0.3,
        "premiumTeAfterOwnedMultiplier": 0.8,
        "profileSummary": "Structured/balance-sensitive; LaPorta suppresses ordinary TE need, not FLEX-worthy TE value.",
        "behavior": {
          "rankTop5Rate": 0.8888888888888888,
          "rankTop10Rate": 0.9722222222222223,
          "rankReach10PlusRate": 0.027777777777777776,
          "adpTop5Rate": 0.6944444444444444,
          "adpReach10PlusRate": 0.16666666666666669
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 36,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 5
            },
            {
              "season": 2021,
              "draftSlot": 5
            },
            {
              "season": 2022,
              "draftSlot": 4
            },
            {
              "season": 2023,
              "draftSlot": 5
            },
            {
              "season": 2024,
              "draftSlot": 7
            },
            {
              "season": 2025,
              "draftSlot": 9
            }
          ],
          "recent2023To2025Share": 0.5,
          "earlyQbDraftRate": 0,
          "premiumTeDraftRate": 0.16666666666666666,
          "positionDoubleTapRate": 0.3333333333333333,
          "previousTurnSamePositionRate": 0.3333333333333333,
          "flexEligibleShareRounds4To6": 0.8888888888888888,
          "positionConcentrationEntropy": 0.8168657103210666,
          "espnRankReach": {
            "mean": 2.5833333333333335,
            "median": 2,
            "p90": 5
          },
          "espnAdpReach": {
            "mean": 3.9444444444444446,
            "median": 2,
            "p90": 11
          },
          "deepConvictionGivenConviction": 0.39171,
          "boardJumpMeanShrunk": 1.935369,
          "convictionJumpMeanShrunk": 9.517155,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.428684,
              "WR": 0.482843,
              "QB": 0.022815,
              "TE": 0.065658
            },
            "R4_6": {
              "RB": 0.307082,
              "WR": 0.433258,
              "QB": 0.136601,
              "TE": 0.123059
            }
          },
          "profileMultipliers": {
            "rb": 1.15,
            "wr": 1.1,
            "qb": 0.8,
            "premium_te": 0.8,
            "te2_flex": 0.8
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 1,
        "draftSlot": 2,
        "manager": "Dan Merrick",
        "teamName": "THE Muskrats",
        "keeper": {
          "name": "George Pickens",
          "position": "WR",
          "round": 6
        },
        "sampleSize": 34,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "BOARD_AWARE",
        "alignment": "FIXED_RANK_LEAN_STRONG",
        "boardModeProbability": 0.712015,
        "convictionModeProbability": 0.287985,
        "espnRankWeight": 0.591839,
        "espnAdpWeight": 0.408161,
        "round1To3PositionProfile": {
          "RB": 0.370297,
          "WR": 0.592352,
          "QB": 0.011354,
          "TE": 0.025997
        },
        "round4To6PositionProfile": {
          "RB": 0.311198,
          "WR": 0.576239,
          "QB": 0.044733,
          "TE": 0.06783
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 0.65,
        "profileSummary": "RB/WR-first; strongest QB pass-through. Bimodal board behavior.",
        "behavior": {
          "rankTop5Rate": 0.7352941176470589,
          "rankTop10Rate": 0.823529411764706,
          "rankReach10PlusRate": 0.17647058823529413,
          "adpTop5Rate": 0.5588235294117647,
          "adpReach10PlusRate": 0.17647058823529413
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 34,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 2
            },
            {
              "season": 2021,
              "draftSlot": 2
            },
            {
              "season": 2022,
              "draftSlot": 3
            },
            {
              "season": 2023,
              "draftSlot": 6
            },
            {
              "season": 2024,
              "draftSlot": 4
            },
            {
              "season": 2025,
              "draftSlot": 5
            }
          ],
          "recent2023To2025Share": 0.5,
          "earlyQbDraftRate": 0,
          "premiumTeDraftRate": 0,
          "positionDoubleTapRate": 0.32142857142857145,
          "previousTurnSamePositionRate": 0.32142857142857145,
          "flexEligibleShareRounds4To6": 1,
          "positionConcentrationEntropy": 0.5546400105221132,
          "espnRankReach": {
            "mean": 4.264705882352941,
            "median": 1,
            "p90": 13
          },
          "espnAdpReach": {
            "mean": 5.911764705882353,
            "median": 4,
            "p90": 15
          },
          "deepConvictionGivenConviction": 0.582786,
          "boardJumpMeanShrunk": 0.929923,
          "convictionJumpMeanShrunk": 12.250572,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.372027,
              "WR": 0.569246,
              "QB": 0.022815,
              "TE": 0.035912
            },
            "R4_6": {
              "RB": 0.297765,
              "WR": 0.527392,
              "QB": 0.085604,
              "TE": 0.08924
            }
          },
          "profileMultipliers": {
            "rb": 1.1,
            "wr": 1.15,
            "qb": 0.55,
            "premium_te": 0.8,
            "te2_flex": 0.65
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 8,
        "draftSlot": 3,
        "manager": "Matt Castleman",
        "teamName": "Team castleman",
        "keeper": {
          "name": "Cam Skattebo",
          "position": "RB",
          "round": 10
        },
        "sampleSize": 34,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "STRONG_BOARD_FOLLOWER",
        "alignment": "FIXED_RANK_LEAN",
        "boardModeProbability": 0.883167,
        "convictionModeProbability": 0.116833,
        "espnRankWeight": 0.566849,
        "espnAdpWeight": 0.433151,
        "round1To3PositionProfile": {
          "RB": 0.385944,
          "WR": 0.504943,
          "QB": 0.069055,
          "TE": 0.040059
        },
        "round4To6PositionProfile": {
          "RB": 0.424149,
          "WR": 0.3384,
          "QB": 0.193464,
          "TE": 0.043987
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 0.65,
        "profileSummary": "Conventional balanced build; premium-QB trigger; highly ESPN-board anchored.",
        "behavior": {
          "rankTop5Rate": 0.9411764705882354,
          "rankTop10Rate": 1,
          "rankReach10PlusRate": 0,
          "adpTop5Rate": 0.676470588235294,
          "adpReach10PlusRate": 0
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 34,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 4
            },
            {
              "season": 2021,
              "draftSlot": 9
            },
            {
              "season": 2022,
              "draftSlot": 8
            },
            {
              "season": 2023,
              "draftSlot": 4
            },
            {
              "season": 2024,
              "draftSlot": 6
            },
            {
              "season": 2025,
              "draftSlot": 2
            }
          ],
          "recent2023To2025Share": 0.47058823529411764,
          "earlyQbDraftRate": 0.16666666666666666,
          "premiumTeDraftRate": 0.16666666666666666,
          "positionDoubleTapRate": 0.25,
          "previousTurnSamePositionRate": 0.25,
          "flexEligibleShareRounds4To6": 0.8125,
          "positionConcentrationEntropy": 0.7804030699937838,
          "espnRankReach": {
            "mean": 1.911764705882353,
            "median": 2,
            "p90": 4
          },
          "espnAdpReach": {
            "mean": 3.1176470588235294,
            "median": 3,
            "p90": 7
          },
          "deepConvictionGivenConviction": 0.370605,
          "boardJumpMeanShrunk": 1.597326,
          "convictionJumpMeanShrunk": 9.84611,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.345115,
              "WR": 0.546583,
              "QB": 0.056809,
              "TE": 0.051493
            },
            "R4_6": {
              "RB": 0.394554,
              "WR": 0.381059,
              "QB": 0.165567,
              "TE": 0.05882
            }
          },
          "profileMultipliers": {
            "rb": 1.15,
            "wr": 0.95,
            "qb": 1.25,
            "premium_te": 0.8,
            "te2_flex": 0.65
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 4,
        "draftSlot": 4,
        "manager": "Matt Hull",
        "teamName": "Deadline Extended",
        "keeper": {
          "name": "Jaylen Warren",
          "position": "RB",
          "round": 9
        },
        "sampleSize": 35,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "BOARD_AWARE",
        "alignment": "FIXED_RANK_LEAN",
        "boardModeProbability": 0.736372,
        "convictionModeProbability": 0.263628,
        "espnRankWeight": 0.543908,
        "espnAdpWeight": 0.456092,
        "round1To3PositionProfile": {
          "RB": 0.264611,
          "WR": 0.603379,
          "QB": 0.105122,
          "TE": 0.026888
        },
        "round4To6PositionProfile": {
          "RB": 0.219957,
          "WR": 0.506821,
          "QB": 0.191266,
          "TE": 0.081957
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 0.7,
        "profileSummary": "WR-forward with strong premium-QB appetite.",
        "behavior": {
          "rankTop5Rate": 0.7428571428571429,
          "rankTop10Rate": 0.8571428571428571,
          "rankReach10PlusRate": 0.14285714285714288,
          "adpTop5Rate": 0.5714285714285715,
          "adpReach10PlusRate": 0.17142857142857143
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 35,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 10
            },
            {
              "season": 2021,
              "draftSlot": 1
            },
            {
              "season": 2022,
              "draftSlot": 7
            },
            {
              "season": 2023,
              "draftSlot": 8
            },
            {
              "season": 2024,
              "draftSlot": 9
            },
            {
              "season": 2025,
              "draftSlot": 1
            }
          ],
          "recent2023To2025Share": 0.4857142857142857,
          "earlyQbDraftRate": 0.3333333333333333,
          "premiumTeDraftRate": 0,
          "positionDoubleTapRate": 0.3448275862068966,
          "previousTurnSamePositionRate": 0.3448275862068966,
          "flexEligibleShareRounds4To6": 0.8235294117647058,
          "positionConcentrationEntropy": 0.809647390717544,
          "espnRankReach": {
            "mean": 4.057142857142857,
            "median": 2,
            "p90": 14
          },
          "espnAdpReach": {
            "mean": 4.714285714285714,
            "median": 4,
            "p90": 11
          },
          "deepConvictionGivenConviction": 0.480258,
          "boardJumpMeanShrunk": 1.377671,
          "convictionJumpMeanShrunk": 10.762469,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.333783,
              "WR": 0.547999,
              "QB": 0.082305,
              "TE": 0.035912
            },
            "R4_6": {
              "RB": 0.278299,
              "WR": 0.461701,
              "QB": 0.150205,
              "TE": 0.109795
            }
          },
          "profileMultipliers": {
            "rb": 0.9,
            "wr": 1.25,
            "qb": 1.45,
            "premium_te": 0.85,
            "te2_flex": 0.7
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 7,
        "draftSlot": 6,
        "manager": "Matt Runge",
        "teamName": "A. To The L.M.",
        "keeper": {
          "name": "Rashee Rice",
          "position": "WR",
          "round": 7
        },
        "sampleSize": 35,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "BOARD_AWARE",
        "alignment": "FIXED_RANK_LEAN_STRONG",
        "boardModeProbability": 0.740667,
        "convictionModeProbability": 0.259333,
        "espnRankWeight": 0.579527,
        "espnAdpWeight": 0.420473,
        "round1To3PositionProfile": {
          "RB": 0.342062,
          "WR": 0.459039,
          "QB": 0.020132,
          "TE": 0.178767
        },
        "round4To6PositionProfile": {
          "RB": 0.314398,
          "WR": 0.470143,
          "QB": 0.137779,
          "TE": 0.07768
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 1.35,
        "profileSummary": "Highest premium-TE appetite; second elite TE remains viable as FLEX; conviction mode matters.",
        "behavior": {
          "rankTop5Rate": 0.7428571428571429,
          "rankTop10Rate": 0.9142857142857143,
          "rankReach10PlusRate": 0.08571428571428572,
          "adpTop5Rate": 0.657142857142857,
          "adpReach10PlusRate": 0.22857142857142856
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 35,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 7
            },
            {
              "season": 2021,
              "draftSlot": 3
            },
            {
              "season": 2022,
              "draftSlot": 2
            },
            {
              "season": 2023,
              "draftSlot": 7
            },
            {
              "season": 2024,
              "draftSlot": 5
            },
            {
              "season": 2025,
              "draftSlot": 7
            }
          ],
          "recent2023To2025Share": 0.4857142857142857,
          "earlyQbDraftRate": 0,
          "premiumTeDraftRate": 0.6666666666666666,
          "positionDoubleTapRate": 0.20689655172413793,
          "previousTurnSamePositionRate": 0.20689655172413793,
          "flexEligibleShareRounds4To6": 0.8235294117647058,
          "positionConcentrationEntropy": 0.8580134688706912,
          "espnRankReach": {
            "mean": 3.5714285714285716,
            "median": 1,
            "p90": 9
          },
          "espnAdpReach": {
            "mean": 4.9714285714285715,
            "median": 3,
            "p90": 16
          },
          "deepConvictionGivenConviction": 0.377172,
          "boardJumpMeanShrunk": 1.241422,
          "convictionJumpMeanShrunk": 10.404105,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.369194,
              "WR": 0.472928,
              "QB": 0.022815,
              "TE": 0.135063
            },
            "R4_6": {
              "RB": 0.326744,
              "WR": 0.466395,
              "QB": 0.150349,
              "TE": 0.056512
            }
          },
          "profileMultipliers": {
            "rb": 1.05,
            "wr": 1.1,
            "qb": 1,
            "premium_te": 1.5,
            "te2_flex": 1.35
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 2,
        "draftSlot": 7,
        "manager": "Jon Merrick",
        "teamName": "Markham Mutts",
        "keeper": {
          "name": "Quinshon Judkins",
          "position": "RB",
          "round": 12
        },
        "sampleSize": 34,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "BOARD_AWARE",
        "alignment": "FIXED_RANK_LEAN",
        "boardModeProbability": 0.735019,
        "convictionModeProbability": 0.264981,
        "espnRankWeight": 0.54286,
        "espnAdpWeight": 0.45714,
        "round1To3PositionProfile": {
          "RB": 0.333358,
          "WR": 0.548234,
          "QB": 0.059685,
          "TE": 0.058723
        },
        "round4To6PositionProfile": {
          "RB": 0.276538,
          "WR": 0.425067,
          "QB": 0.170957,
          "TE": 0.127437
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 1.15,
        "profileSummary": "Adaptive/high-entropy BPA; flatter selection distribution.",
        "behavior": {
          "rankTop5Rate": 0.7352941176470589,
          "rankTop10Rate": 0.8823529411764706,
          "rankReach10PlusRate": 0.11764705882352942,
          "adpTop5Rate": 0.7058823529411765,
          "adpReach10PlusRate": 0.17647058823529413
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 34,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 6
            },
            {
              "season": 2021,
              "draftSlot": 6
            },
            {
              "season": 2022,
              "draftSlot": 10
            },
            {
              "season": 2023,
              "draftSlot": 1
            },
            {
              "season": 2024,
              "draftSlot": 8
            },
            {
              "season": 2025,
              "draftSlot": 8
            }
          ],
          "recent2023To2025Share": 0.5,
          "earlyQbDraftRate": 0.16666666666666666,
          "premiumTeDraftRate": 0.16666666666666666,
          "positionDoubleTapRate": 0.42857142857142855,
          "previousTurnSamePositionRate": 0.42857142857142855,
          "flexEligibleShareRounds4To6": 0.875,
          "positionConcentrationEntropy": 0.8553691366961442,
          "espnRankReach": {
            "mean": 3.6470588235294117,
            "median": 2,
            "p90": 10
          },
          "espnAdpReach": {
            "mean": 4.176470588235294,
            "median": 2,
            "p90": 11
          },
          "deepConvictionGivenConviction": 0.460039,
          "boardJumpMeanShrunk": 1.123231,
          "convictionJumpMeanShrunk": 10.75061,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.35078,
              "WR": 0.549416,
              "QB": 0.048311,
              "TE": 0.051493
            },
            "R4_6": {
              "RB": 0.30089,
              "WR": 0.440475,
              "QB": 0.143086,
              "TE": 0.115549
            }
          },
          "profileMultipliers": {
            "rb": 1,
            "wr": 1.05,
            "qb": 1.3,
            "premium_te": 1.2,
            "te2_flex": 1.15
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 5,
        "draftSlot": 8,
        "manager": "Matt Sloka",
        "teamName": "Team Sloka",
        "keeper": {
          "name": "Luther Burden III",
          "position": "WR",
          "round": 14
        },
        "sampleSize": 34,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "CONTROLLED_INDEPENDENCE",
        "alignment": "FIXED_RANK_LEAN_STRONG",
        "boardModeProbability": 0.681694,
        "convictionModeProbability": 0.318306,
        "espnRankWeight": 0.737437,
        "espnAdpWeight": 0.262563,
        "round1To3PositionProfile": {
          "RB": 0.280933,
          "WR": 0.656493,
          "QB": 0.017119,
          "TE": 0.045455
        },
        "round4To6PositionProfile": {
          "RB": 0.1859,
          "WR": 0.635137,
          "QB": 0.107986,
          "TE": 0.070977
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 0.95,
        "profileSummary": "Young-WR/upside hunter; low literal Top-1 rate but usually operates inside visible ESPN rank bucket.",
        "behavior": {
          "rankTop5Rate": 0.676470588235294,
          "rankTop10Rate": 0.9411764705882354,
          "rankReach10PlusRate": 0.05882352941176471,
          "adpTop5Rate": 0.4411764705882353,
          "adpReach10PlusRate": 0.32352941176470584
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 34,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 1
            },
            {
              "season": 2021,
              "draftSlot": 7
            },
            {
              "season": 2022,
              "draftSlot": 5
            },
            {
              "season": 2023,
              "draftSlot": 9
            },
            {
              "season": 2024,
              "draftSlot": 3
            },
            {
              "season": 2025,
              "draftSlot": 4
            }
          ],
          "recent2023To2025Share": 0.5294117647058824,
          "earlyQbDraftRate": 0,
          "premiumTeDraftRate": 0.16666666666666666,
          "positionDoubleTapRate": 0.35714285714285715,
          "previousTurnSamePositionRate": 0.35714285714285715,
          "flexEligibleShareRounds4To6": 0.875,
          "positionConcentrationEntropy": 0.7089080251643641,
          "espnRankReach": {
            "mean": 3.5294117647058822,
            "median": 3,
            "p90": 9
          },
          "espnAdpReach": {
            "mean": 8.294117647058824,
            "median": 6,
            "p90": 15
          },
          "deepConvictionGivenConviction": 0.291166,
          "boardJumpMeanShrunk": 1.707576,
          "convictionJumpMeanShrunk": 8.414832,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.353613,
              "WR": 0.572078,
              "QB": 0.022815,
              "TE": 0.051493
            },
            "R4_6": {
              "RB": 0.231268,
              "WR": 0.547021,
              "QB": 0.142242,
              "TE": 0.079469
            }
          },
          "profileMultipliers": {
            "rb": 0.9,
            "wr": 1.3,
            "qb": 0.85,
            "premium_te": 1,
            "te2_flex": 0.95
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 11,
        "draftSlot": 9,
        "manager": "Kyle Cavanaugh",
        "teamName": "TalkToMeGoose",
        "keeper": {
          "name": "Chris Olave",
          "position": "WR",
          "round": 9
        },
        "sampleSize": 30,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024
        ],
        "sampleConfidence": "MEDIUM",
        "boardStyle": "CONTROLLED_INDEPENDENCE",
        "alignment": "ADP_LEAN",
        "boardModeProbability": 0.653554,
        "convictionModeProbability": 0.346446,
        "espnRankWeight": 0.469145,
        "espnAdpWeight": 0.530855,
        "round1To3PositionProfile": {
          "RB": 0.56055,
          "WR": 0.333809,
          "QB": 0.026132,
          "TE": 0.07951
        },
        "round4To6PositionProfile": {
          "RB": 0.326772,
          "WR": 0.40391,
          "QB": 0.154756,
          "TE": 0.114562
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 1.15,
        "profileSummary": "Olave R9 keeper; RB foundation + opportunistic premium QB/TE; most ADP-leaning relative to fixed rank.",
        "behavior": {
          "rankTop5Rate": 0.6,
          "rankTop10Rate": 0.8,
          "rankReach10PlusRate": 0.2,
          "adpTop5Rate": 0.5333333333333333,
          "adpReach10PlusRate": 0.2
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 30,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 8
            },
            {
              "season": 2021,
              "draftSlot": 8
            },
            {
              "season": 2022,
              "draftSlot": 1
            },
            {
              "season": 2023,
              "draftSlot": 10
            },
            {
              "season": 2024,
              "draftSlot": 1
            }
          ],
          "recent2023To2025Share": 0.4,
          "earlyQbDraftRate": 0,
          "premiumTeDraftRate": 0.2,
          "positionDoubleTapRate": 0.44,
          "previousTurnSamePositionRate": 0.44,
          "flexEligibleShareRounds4To6": 0.8666666666666667,
          "positionConcentrationEntropy": 0.7814033158465872,
          "espnRankReach": {
            "mean": 5.4,
            "median": 3,
            "p90": 17
          },
          "espnAdpReach": {
            "mean": 5.033333333333333,
            "median": 4,
            "p90": 11
          },
          "deepConvictionGivenConviction": 0.513591,
          "boardJumpMeanShrunk": 1.378828,
          "convictionJumpMeanShrunk": 11.441583,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.482099,
              "WR": 0.424113,
              "QB": 0.025406,
              "TE": 0.068382
            },
            "R4_6": {
              "RB": 0.269401,
              "WR": 0.491924,
              "QB": 0.144227,
              "TE": 0.094448
            }
          },
          "profileMultipliers": {
            "rb": 1.3,
            "wr": 0.88,
            "qb": 1.15,
            "premium_te": 1.3,
            "te2_flex": 1.15
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      },
      {
        "espnTeamId": 12,
        "draftSlot": 10,
        "manager": "Brenden Lautenbach",
        "teamName": "The Terryble Towels",
        "keeper": {
          "name": "Javonte Williams",
          "position": "RB",
          "round": 9
        },
        "sampleSize": 36,
        "seasonsRepresented": [
          2020,
          2021,
          2022,
          2023,
          2024,
          2025
        ],
        "sampleConfidence": "HIGH",
        "boardStyle": "HIGH_CONVICTION_INDEPENDENT",
        "alignment": "FIXED_RANK_LEAN",
        "boardModeProbability": 0.57361,
        "convictionModeProbability": 0.42639,
        "espnRankWeight": 0.548683,
        "espnAdpWeight": 0.451317,
        "round1To3PositionProfile": {
          "RB": 0.232492,
          "WR": 0.616051,
          "QB": 0.066399,
          "TE": 0.085058
        },
        "round4To6PositionProfile": {
          "RB": 0.169285,
          "WR": 0.478053,
          "QB": 0.195786,
          "TE": 0.156876
        },
        "ordinaryTeNeedMultiplier": 1,
        "premiumTeAfterOwnedMultiplier": 1.15,
        "profileSummary": "Strongest conviction/reach behavior; pass-catcher/early-QB/TE appetite.",
        "behavior": {
          "rankTop5Rate": 0.5,
          "rankTop10Rate": 0.6944444444444444,
          "rankReach10PlusRate": 0.3055555555555556,
          "adpTop5Rate": 0.5277777777777778,
          "adpReach10PlusRate": 0.41666666666666663
        },
        "historicalEvidence": {
          "sampleSizeRounds1To6": 36,
          "seasonsRepresented": [
            2020,
            2021,
            2022,
            2023,
            2024,
            2025
          ],
          "draftSlotHistory": [
            {
              "season": 2020,
              "draftSlot": 3
            },
            {
              "season": 2021,
              "draftSlot": 4
            },
            {
              "season": 2022,
              "draftSlot": 6
            },
            {
              "season": 2023,
              "draftSlot": 3
            },
            {
              "season": 2024,
              "draftSlot": 2
            },
            {
              "season": 2025,
              "draftSlot": 10
            }
          ],
          "recent2023To2025Share": 0.5,
          "earlyQbDraftRate": 0.16666666666666666,
          "premiumTeDraftRate": 0.3333333333333333,
          "positionDoubleTapRate": 0.3,
          "previousTurnSamePositionRate": 0.3,
          "flexEligibleShareRounds4To6": 0.7777777777777778,
          "positionConcentrationEntropy": 0.8685543318502539,
          "espnRankReach": {
            "mean": 6.222222222222222,
            "median": 7,
            "p90": 13
          },
          "espnAdpReach": {
            "mean": 6.916666666666667,
            "median": 4,
            "p90": 16
          },
          "deepConvictionGivenConviction": 0.583749,
          "boardJumpMeanShrunk": 1.254411,
          "convictionJumpMeanShrunk": 10.890015,
          "historicalPositionPosterior": {
            "R1_3": {
              "RB": 0.298373,
              "WR": 0.569246,
              "QB": 0.056809,
              "TE": 0.075573
            },
            "R4_6": {
              "RB": 0.224929,
              "WR": 0.457337,
              "QB": 0.173428,
              "TE": 0.144306
            }
          },
          "profileMultipliers": {
            "rb": 0.9,
            "wr": 1.25,
            "qb": 1.35,
            "premium_te": 1.3,
            "te2_flex": 1.15
          },
          "seasonWeights": {
            "2020": 0.55,
            "2021": 0.65,
            "2022": 0.75,
            "2023": 0.9,
            "2024": 1.05,
            "2025": 1.2
          },
          "keeperEffectPolicy": "Confirmed keeper initializes roster needs; no separate keeper residual is promoted."
        }
      }
    ],
    "playerMarket": [
      {
        "playerId": 1,
        "espnDefaultRank": 1,
        "espnAdp": 1.35,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 2,
        "espnDefaultRank": 2,
        "espnAdp": 2.39,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 3,
        "espnDefaultRank": 3,
        "espnAdp": 4.3,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 4,
        "espnDefaultRank": 4,
        "espnAdp": 5.28,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 5,
        "espnDefaultRank": 7,
        "espnAdp": 7.66,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 6,
        "espnDefaultRank": 5,
        "espnAdp": 6.42,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 7,
        "espnDefaultRank": 6,
        "espnAdp": 6.15,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 8,
        "espnDefaultRank": 8,
        "espnAdp": 8.34,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 9,
        "espnDefaultRank": 9,
        "espnAdp": 10.56,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 10,
        "espnDefaultRank": 11,
        "espnAdp": 11.67,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 11,
        "espnDefaultRank": 12,
        "espnAdp": 12.63,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 12,
        "espnDefaultRank": 10,
        "espnAdp": 12.12,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 13,
        "espnDefaultRank": 15,
        "espnAdp": 14.19,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 14,
        "espnDefaultRank": 14,
        "espnAdp": 17.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 15,
        "espnDefaultRank": 13,
        "espnAdp": 19.85,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 16,
        "espnDefaultRank": 16,
        "espnAdp": 16.96,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 17,
        "espnDefaultRank": 17,
        "espnAdp": 19.91,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 18,
        "espnDefaultRank": 18,
        "espnAdp": 21.42,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 19,
        "espnDefaultRank": 25,
        "espnAdp": 24.82,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 20,
        "espnDefaultRank": 19,
        "espnAdp": 21.9,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 21,
        "espnDefaultRank": 22,
        "espnAdp": 24,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 22,
        "espnDefaultRank": 23,
        "espnAdp": 25.95,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 23,
        "espnDefaultRank": 20,
        "espnAdp": 22.35,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 24,
        "espnDefaultRank": 28,
        "espnAdp": 28.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 25,
        "espnDefaultRank": 26,
        "espnAdp": 19.57,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 26,
        "espnDefaultRank": 24,
        "espnAdp": 29.83,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 27,
        "espnDefaultRank": 21,
        "espnAdp": 25.8,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 28,
        "espnDefaultRank": 33,
        "espnAdp": 34.56,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 29,
        "espnDefaultRank": 32,
        "espnAdp": 36.79,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 30,
        "espnDefaultRank": 27,
        "espnAdp": 28.16,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 31,
        "espnDefaultRank": 30,
        "espnAdp": 35.81,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 32,
        "espnDefaultRank": 35,
        "espnAdp": 37.31,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 33,
        "espnDefaultRank": 31,
        "espnAdp": 33.56,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 34,
        "espnDefaultRank": 93,
        "espnAdp": 54.26,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 35,
        "espnDefaultRank": 44,
        "espnAdp": 51.3,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 36,
        "espnDefaultRank": 36,
        "espnAdp": 41.78,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 37,
        "espnDefaultRank": 38,
        "espnAdp": 44.06,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 38,
        "espnDefaultRank": 29,
        "espnAdp": 37.18,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 39,
        "espnDefaultRank": 41,
        "espnAdp": 46.75,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 40,
        "espnDefaultRank": 43,
        "espnAdp": 42.87,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 41,
        "espnDefaultRank": 39,
        "espnAdp": 45.47,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 42,
        "espnDefaultRank": 34,
        "espnAdp": 42.33,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 43,
        "espnDefaultRank": 46,
        "espnAdp": 52.78,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 44,
        "espnDefaultRank": 49,
        "espnAdp": 35.36,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 45,
        "espnDefaultRank": 42,
        "espnAdp": 45.48,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 46,
        "espnDefaultRank": 47,
        "espnAdp": 54.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 47,
        "espnDefaultRank": 40,
        "espnAdp": 50.28,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 48,
        "espnDefaultRank": 45,
        "espnAdp": 46.34,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 49,
        "espnDefaultRank": 50,
        "espnAdp": 56.92,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 50,
        "espnDefaultRank": 56,
        "espnAdp": 51.93,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 51,
        "espnDefaultRank": 52,
        "espnAdp": 61.06,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 52,
        "espnDefaultRank": 66,
        "espnAdp": 76.19,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 53,
        "espnDefaultRank": 51,
        "espnAdp": 63.66,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 54,
        "espnDefaultRank": 53,
        "espnAdp": 62.23,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 55,
        "espnDefaultRank": 55,
        "espnAdp": 64.73,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 56,
        "espnDefaultRank": 62,
        "espnAdp": 47.42,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 57,
        "espnDefaultRank": 48,
        "espnAdp": 63.78,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 58,
        "espnDefaultRank": 58,
        "espnAdp": 64.86,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 59,
        "espnDefaultRank": 70,
        "espnAdp": 54.47,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 60,
        "espnDefaultRank": 60,
        "espnAdp": 52.59,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 61,
        "espnDefaultRank": 64,
        "espnAdp": 79.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 62,
        "espnDefaultRank": 68,
        "espnAdp": 86.52,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 63,
        "espnDefaultRank": 54,
        "espnAdp": 69.96,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 64,
        "espnDefaultRank": 76,
        "espnAdp": 53.96,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 65,
        "espnDefaultRank": 85,
        "espnAdp": 90.79,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 66,
        "espnDefaultRank": 67,
        "espnAdp": 76.94,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 67,
        "espnDefaultRank": 72,
        "espnAdp": 79.9,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 68,
        "espnDefaultRank": 92,
        "espnAdp": 72.77,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 69,
        "espnDefaultRank": 87,
        "espnAdp": 90.84,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 70,
        "espnDefaultRank": 69,
        "espnAdp": 80.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 71,
        "espnDefaultRank": 77,
        "espnAdp": 71.37,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 72,
        "espnDefaultRank": 81,
        "espnAdp": 90.19,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 73,
        "espnDefaultRank": 75,
        "espnAdp": 85.67,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 74,
        "espnDefaultRank": 79,
        "espnAdp": 67.85,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 75,
        "espnDefaultRank": 80,
        "espnAdp": 73.89,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 76,
        "espnDefaultRank": 126,
        "espnAdp": 90.95,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 77,
        "espnDefaultRank": 74,
        "espnAdp": 92.3,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 78,
        "espnDefaultRank": 114,
        "espnAdp": 112.81,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 79,
        "espnDefaultRank": 107,
        "espnAdp": 92.39,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 80,
        "espnDefaultRank": 102,
        "espnAdp": 89.56,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 81,
        "espnDefaultRank": 78,
        "espnAdp": 81.35,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 82,
        "espnDefaultRank": 95,
        "espnAdp": 96.59,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 83,
        "espnDefaultRank": 97,
        "espnAdp": 102.11,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 84,
        "espnDefaultRank": 108,
        "espnAdp": 109.22,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 85,
        "espnDefaultRank": 89,
        "espnAdp": 77.88,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 86,
        "espnDefaultRank": 73,
        "espnAdp": 90.21,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 87,
        "espnDefaultRank": 120,
        "espnAdp": 97.88,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 88,
        "espnDefaultRank": 104,
        "espnAdp": 107.19,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 89,
        "espnDefaultRank": 118,
        "espnAdp": 125.66,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 90,
        "espnDefaultRank": 100,
        "espnAdp": 82.26,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 91,
        "espnDefaultRank": 122,
        "espnAdp": 113.19,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 92,
        "espnDefaultRank": 106,
        "espnAdp": 105.88,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 93,
        "espnDefaultRank": 111,
        "espnAdp": 108.22,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 94,
        "espnDefaultRank": 133,
        "espnAdp": 127.45,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 95,
        "espnDefaultRank": 119,
        "espnAdp": 119.9,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 96,
        "espnDefaultRank": 127,
        "espnAdp": 137.23,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 97,
        "espnDefaultRank": 138,
        "espnAdp": 127.68,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 98,
        "espnDefaultRank": 88,
        "espnAdp": 104.17,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 99,
        "espnDefaultRank": 125,
        "espnAdp": 124.35,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 100,
        "espnDefaultRank": 137,
        "espnAdp": 133.19,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 101,
        "espnDefaultRank": 148,
        "espnAdp": 130.09,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 102,
        "espnDefaultRank": 145,
        "espnAdp": 135.91,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 103,
        "espnDefaultRank": 91,
        "espnAdp": 115.48,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 104,
        "espnDefaultRank": 124,
        "espnAdp": 109.11,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 105,
        "espnDefaultRank": 131,
        "espnAdp": 95.23,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 106,
        "espnDefaultRank": 141,
        "espnAdp": 90.81,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 107,
        "espnDefaultRank": 157,
        "espnAdp": 130.87,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 108,
        "espnDefaultRank": 117,
        "espnAdp": 111.18,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 109,
        "espnDefaultRank": 112,
        "espnAdp": 122.29,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 110,
        "espnDefaultRank": 150,
        "espnAdp": 137.86,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 111,
        "espnDefaultRank": 121,
        "espnAdp": 126.12,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 112,
        "espnDefaultRank": 132,
        "espnAdp": 107.81,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 113,
        "espnDefaultRank": 139,
        "espnAdp": 99.71,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 114,
        "espnDefaultRank": 110,
        "espnAdp": 116.72,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 115,
        "espnDefaultRank": 147,
        "espnAdp": 123.37,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 116,
        "espnDefaultRank": 161,
        "espnAdp": 139.47,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 117,
        "espnDefaultRank": 134,
        "espnAdp": 104.06,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 118,
        "espnDefaultRank": 152,
        "espnAdp": 141.9,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 119,
        "espnDefaultRank": 140,
        "espnAdp": 109.18,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 120,
        "espnDefaultRank": 164,
        "espnAdp": 146.68,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 121,
        "espnDefaultRank": 156,
        "espnAdp": 155.89,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 122,
        "espnDefaultRank": 154,
        "espnAdp": 148.29,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 123,
        "espnDefaultRank": 143,
        "espnAdp": 139.71,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 124,
        "espnDefaultRank": 159,
        "espnAdp": 136.05,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 125,
        "espnDefaultRank": 153,
        "espnAdp": 125.74,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 126,
        "espnDefaultRank": 151,
        "espnAdp": 129.34,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 127,
        "espnDefaultRank": 223,
        "espnAdp": 168.1,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 128,
        "espnDefaultRank": 183,
        "espnAdp": 164.95,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 129,
        "espnDefaultRank": 130,
        "espnAdp": 139.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 130,
        "espnDefaultRank": 160,
        "espnAdp": 146.91,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 131,
        "espnDefaultRank": 175,
        "espnAdp": 145.99,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 132,
        "espnDefaultRank": 109,
        "espnAdp": 118.96,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 133,
        "espnDefaultRank": 163,
        "espnAdp": 141.06,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 134,
        "espnDefaultRank": 167,
        "espnAdp": 151.49,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 135,
        "espnDefaultRank": 165,
        "espnAdp": 153.25,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 136,
        "espnDefaultRank": 195,
        "espnAdp": 162.85,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 137,
        "espnDefaultRank": 203,
        "espnAdp": 155.68,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 138,
        "espnDefaultRank": 158,
        "espnAdp": 153.02,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 139,
        "espnDefaultRank": 192,
        "espnAdp": 151.46,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 140,
        "espnDefaultRank": 228,
        "espnAdp": 169.37,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 141,
        "espnDefaultRank": 214,
        "espnAdp": 160.04,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 142,
        "espnDefaultRank": 191,
        "espnAdp": 158.96,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 143,
        "espnDefaultRank": 201,
        "espnAdp": 165.64,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 144,
        "espnDefaultRank": 215,
        "espnAdp": 168.79,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 145,
        "espnDefaultRank": 229,
        "espnAdp": 164.24,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 146,
        "espnDefaultRank": 208,
        "espnAdp": 167.55,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 147,
        "espnDefaultRank": 173,
        "espnAdp": 169.15,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 148,
        "espnDefaultRank": 222,
        "espnAdp": 167.52,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 149,
        "espnDefaultRank": 171,
        "espnAdp": 165.08,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 150,
        "espnDefaultRank": 237,
        "espnAdp": 169.72,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 151,
        "espnDefaultRank": 90,
        "espnAdp": 140.02,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 152,
        "espnDefaultRank": 207,
        "espnAdp": 167.56,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 153,
        "espnDefaultRank": 189,
        "espnAdp": 160.38,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 154,
        "espnDefaultRank": 226,
        "espnAdp": 169.12,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 155,
        "espnDefaultRank": 177,
        "espnAdp": 159.42,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 156,
        "espnDefaultRank": 184,
        "espnAdp": 158.09,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 157,
        "espnDefaultRank": 213,
        "espnAdp": 168.34,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 158,
        "espnDefaultRank": 221,
        "espnAdp": 170.66,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 159,
        "espnDefaultRank": 206,
        "espnAdp": 169.1,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 160,
        "espnDefaultRank": 283,
        "espnAdp": 162.24,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 161,
        "espnDefaultRank": 199,
        "espnAdp": 148.13,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 162,
        "espnDefaultRank": 227,
        "espnAdp": 171.07,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 163,
        "espnDefaultRank": 235,
        "espnAdp": 170.97,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 164,
        "espnDefaultRank": 297,
        "espnAdp": 168.62,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 165,
        "espnDefaultRank": 311,
        "espnAdp": 170.15,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 166,
        "espnDefaultRank": 230,
        "espnAdp": 170.98,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 167,
        "espnDefaultRank": 236,
        "espnAdp": 171.65,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 168,
        "espnDefaultRank": 220,
        "espnAdp": 171.05,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 169,
        "espnDefaultRank": 238,
        "espnAdp": 171.04,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 170,
        "espnDefaultRank": 280,
        "espnAdp": 165.25,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 171,
        "espnDefaultRank": 216,
        "espnAdp": 168.29,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 172,
        "espnDefaultRank": 212,
        "espnAdp": 171.84,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 173,
        "espnDefaultRank": 200,
        "espnAdp": 161.15,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 174,
        "espnDefaultRank": 312,
        "espnAdp": 169.69,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 175,
        "espnDefaultRank": 299,
        "espnAdp": 171.09,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 176,
        "espnDefaultRank": 371,
        "espnAdp": 170.41,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 177,
        "espnDefaultRank": 313,
        "espnAdp": 168.9,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 178,
        "espnDefaultRank": 276,
        "espnAdp": 168.64,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 179,
        "espnDefaultRank": 293,
        "espnAdp": 171.17,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 180,
        "espnDefaultRank": 305,
        "espnAdp": 170.59,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 181,
        "espnDefaultRank": 306,
        "espnAdp": 170.43,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 182,
        "espnDefaultRank": 315,
        "espnAdp": 169.22,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 183,
        "espnDefaultRank": 285,
        "espnAdp": 171.1,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 184,
        "espnDefaultRank": 342,
        "espnAdp": 169.93,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 185,
        "espnDefaultRank": 365,
        "espnAdp": 170.47,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 186,
        "espnDefaultRank": 232,
        "espnAdp": 171.39,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 187,
        "espnDefaultRank": 322,
        "espnAdp": 170.17,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 188,
        "espnDefaultRank": 304,
        "espnAdp": 171.2,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 189,
        "espnDefaultRank": 176,
        "espnAdp": 162.72,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 190,
        "espnDefaultRank": 211,
        "espnAdp": null,
        "marketCoverage": "default-rank-only"
      },
      {
        "playerId": 191,
        "espnDefaultRank": 319,
        "espnAdp": 170.67,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 192,
        "espnDefaultRank": 205,
        "espnAdp": 168.34,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 193,
        "espnDefaultRank": 302,
        "espnAdp": 170.89,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 194,
        "espnDefaultRank": 273,
        "espnAdp": 168.54,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 195,
        "espnDefaultRank": 346,
        "espnAdp": 170.33,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 196,
        "espnDefaultRank": 355,
        "espnAdp": 170.4,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 197,
        "espnDefaultRank": 310,
        "espnAdp": 170.75,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 198,
        "espnDefaultRank": 331,
        "espnAdp": 170.51,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 199,
        "espnDefaultRank": 397,
        "espnAdp": 170.45,
        "marketCoverage": "matched-current-espn"
      },
      {
        "playerId": 200,
        "espnDefaultRank": 317,
        "espnAdp": 169.97,
        "marketCoverage": "matched-current-espn"
      }
    ]
  });
})();
