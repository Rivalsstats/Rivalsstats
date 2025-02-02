# DataScience_Projekt



Next Meeting: 13.11.2024



## Verwendung von Renv für das Paketmanagement

Für das Management und die Synchronisierung der R-Pakete verwenden wir `renv` [Doku](https://rstudio.github.io/renv/articles/renv.html). Diese Vorgehensweise stellt sicher, dass alle Teammitglieder mit denselben Paketversionen arbeiten und so Konsistenz in unseren Projekten gewährleistet ist.

### Einrichtung von Renv

1. **Installation von Renv**: Falls `renv` noch nicht installiert ist, kannst du es mit folgendem Befehl installieren:
```R
install.packages("renv")
```
Snapshot der Pakete erstellen: Nach der Installation oder Aktualisierung von R-Paketen ist es wichtig, die aktuellen Paketversionen zu speichern. Dies geschieht mit dem Befehl:

```R
renv::snapshot()
```
Dieser Befehl erstellt eine renv.lock-Datei, die die Informationen zu den installierten Paketen enthält.

Änderungen committen: Stelle sicher, dass du die renv.lock-Datei zu deinem Versionskontrollsystem hinzufügst und die Änderungen commitest. So können andere Teammitglieder die gleichen Paketversionen verwenden.

Wiederherstellung nach einem Pull: Wenn du Änderungen von einem anderen Teammitglied pullst, solltest du die Pakete mit dem folgenden Befehl wiederherstellen:

```R
renv::restore()
```
Dadurch werden die in der renv.lock-Datei definierten Pakete installiert.

Hinweise
Achte darauf, dass du vor einem Commit mit neuen Bibiliotheken immer renv::snapshot() ausführst, um sicherzustellen, dass die renv.lock-Datei immer auf dem neuesten Stand ist.
Nach dem Ausführen von renv::restore() werden alle Pakete gemäß der renv.lock-Datei installiert. Bei Problemen kann es hilfreich sein, den R-Workspace neu zu starten.
Durch die Verwendung von renv stellen wir sicher, dass unser R-Projekt zuverlässig und konsistent bleibt.


Sources:


[Plotly](https://plotly.com/r/)
[R_Markdown help](https://bookdown.org/yihui/bookdown/)
[R_Markdown help2](https://holtzy.github.io/Pimp-my-rmd/)


[Example of videogame Project](https://florian-reichle.de/VisualDataAnalysis_VideoGameSales/VDAProjekt.html)
