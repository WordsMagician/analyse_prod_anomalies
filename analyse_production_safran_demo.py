from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = Path("dataset_production_safran_demo.csv")


def detect_cycle_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Détecte les anomalies simples par z-score au sein de chaque type de pièce."""
    stats = df.groupby("piece_type")["cycle_time_min"].agg(["mean", "std"]).rename(
        columns={"mean": "piece_mean", "std": "piece_std"}
    )
    merged = df.merge(stats, left_on="piece_type", right_index=True, how="left")
    merged["z_score"] = (merged["cycle_time_min"] - merged["piece_mean"]) / merged["piece_std"]
    return merged[merged["z_score"].abs() >= 2.5].copy()


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {DATA_PATH.resolve()}\n"
            "Place le CSV dans le même dossier que ce script."
        )

    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])

    # Colonnes dérivées
    df["is_defect"] = df["status"].eq("NOK").astype(int)
    df["date"] = df["timestamp"].dt.date

    print("=" * 70)
    print("ANALYSE PRODUCTION - DEMO STYLE INDUSTRIEL")
    print("=" * 70)
    print(f"Nombre de lignes : {len(df)}")
    print(f"Période : {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print()

    # Vue globale
    defect_rate_global = df["is_defect"].mean() * 100
    print(f"Taux de défaut global : {defect_rate_global:.2f} %")
    print(f"Temps de cycle moyen global : {df['cycle_time_min'].mean():.2f} min")
    print()

    # Taux de défaut par machine
    per_machine = (
        df.groupby("machine")
          .agg(
              nb_pieces=("status", "size"),
              taux_defaut=("is_defect", "mean"),
              cycle_moyen=("cycle_time_min", "mean"),
          )
          .sort_values("taux_defaut", ascending=False)
    )
    per_machine["taux_defaut"] = per_machine["taux_defaut"] * 100

    print("Taux de défaut par machine :")
    print(per_machine.round(2))
    print()

    # Top défauts
    defect_breakdown = (
        df[df["status"] == "NOK"]["defect_type"]
        .value_counts()
        .rename_axis("defect_type")
        .reset_index(name="count")
    )
    print("Top défauts :")
    print(defect_breakdown.head(10).to_string(index=False))
    print()

    # Dérive récente vs historique
    split_date = df["timestamp"].max() - pd.Timedelta(days=7)
    recent = df[df["timestamp"] >= split_date]
    historical = df[df["timestamp"] < split_date]

    rec_machine = recent.groupby("machine")["is_defect"].mean() * 100
    hist_machine = historical.groupby("machine")["is_defect"].mean() * 100
    drift = pd.concat([hist_machine.rename("historique_%"), rec_machine.rename("recent_%")], axis=1)
    drift["ecart_points"] = drift["recent_%"] - drift["historique_%"]
    drift = drift.sort_values("ecart_points", ascending=False)

    print("Évolution du taux de défaut (7 derniers jours vs historique) :")
    print(drift.round(2))
    print()

    # Détection anomalies cycle
    anomalies = detect_cycle_anomalies(df)
    print(f"Nombre d'anomalies de temps de cycle détectées : {len(anomalies)}")
    if not anomalies.empty:
        print("Exemples :")
        print(
            anomalies[["timestamp", "machine", "piece_type", "cycle_time_min", "z_score"]]
            .sort_values("z_score", ascending=False)
            .head(10)
            .round({"cycle_time_min": 2, "z_score": 2})
            .to_string(index=False)
        )
    print()

    # Insight auto simple
    if not drift.empty:
        worst_machine = drift.index[0]
        worst_delta = drift.iloc[0]["ecart_points"]
        if pd.notna(worst_delta) and worst_delta > 2:
            print(
                f"ALERTE : la machine {worst_machine} montre une hausse de "
                f"{worst_delta:.2f} points de défaut sur les 7 derniers jours."
            )
        else:
            print("Pas de dérive majeure détectée sur les taux de défaut récents.")
    print()

    # Graphique 1 : défaut par machine
    plt.figure(figsize=(8, 5))
    per_machine["taux_defaut"].sort_values(ascending=False).plot(kind="bar")
    plt.title("Taux de défaut par machine (%)")
    plt.ylabel("Pourcentage")
    plt.xlabel("Machine")
    plt.tight_layout()
    plt.show()

    # Graphique 2 : cycle moyen journalier par machine
    daily_cycle = (
        df.groupby(["date", "machine"])["cycle_time_min"]
        .mean()
        .reset_index()
    )
    pivot_cycle = daily_cycle.pivot(index="date", columns="machine", values="cycle_time_min")

    plt.figure(figsize=(10, 5))
    for machine in pivot_cycle.columns:
        plt.plot(pivot_cycle.index, pivot_cycle[machine], label=machine)
    plt.title("Temps de cycle moyen journalier par machine")
    plt.ylabel("Minutes")
    plt.xlabel("Date")
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()