# Publicité Riders Fanatics

## Préproduction

Un seul emplacement responsive, identifié comme aperçu, est placé après le contenu et avant le pied de page, notamment sur les Bike Checks. Aucun popup, aucune surimpression, aucun script publicitaire, cookie publicitaire ou impression AdSense dans ce mode. La préproduction force toujours cet aperçu, même si RF_ADS_MODE=live. Le refus des traceurs ne bloque pas le contenu.

La copie locale historique contient des modifications non enregistrées et n'a pas été écrasée. Cette évolution part de la branche preprod distante, dans une copie de travail isolée.

## Activation ultérieure des annonces réelles

Aucun déploiement de production n'est effectué par cette modification. Une promotion explicite et une configuration du processus de construction de production seront nécessaires.

- RF_ADS_MODE=live : activation explicite au moment de la construction. Par défaut : preview.
- RF_ADS_CLIENT : identifiant éditeur. Valeur existante : ca-pub-6372404738608947.
- RF_ADS_SLOT : identifiant de l'emplacement responsive. Valeur existante : 7556439197.
- Un identifiant vide ou mal formé conserve l'aperçu. La présence des identifiants existants ne prouve pas l'approbation du compte, du domaine ou de l'emplacement.
- Vérifier le compte AdSense et l'approbation de ridersfanatics.com. Si l'éditeur change, actualiser ads.txt avec la ligne fournie par AdSense.
- Installer séparément le code officiel d'une CMP Google certifiée, compatible TCF, avant d'activer les annonces. Le chargeur actuel attend __tcfapi et googlefc.showRevocationMessage : utiliser le message européen Google Privacy & messaging, ou adapter explicitement ce raccordement pour une autre CMP. Aucun faux bandeau local n'est présenté comme CMP certifiée.
- Publier/configurer dans cette CMP les choix accepter/refuser aussi accessibles l'un que l'autre, les fournisseurs et finalités, la durée de conservation des choix et le retrait du consentement. Mettre la politique de confidentialité en accord avec les traitements et durées réellement configurés.
- Le chargeur impose le consentement explicite au fournisseur Google (755) et aux finalités 1, 2, 3, 4, 7, 9, 10, et respecte les restrictions éditeur. Cette politique volontairement restrictive ne diffuse aucune annonce sans consentement, même hors EEE. CMP absente, refus, choix inconnu ou configuration incomplète : aucune requête AdSense.
- Le bouton Privacy and cookie settings est disponible sur chaque page disposant d'une unité réelle et d'une CMP prête. Le contrôle natif de la CMP est conservé. Le retrait recharge la page pour arrêter les scripts publicitaires déjà chargés ; il n'efface pas les cookies appartenant à Google.
- Désactiver les annonces automatiques, ancres et interstitiels dans AdSense pour conserver le seul emplacement manuel. Garder les annonces réelles hors de la préproduction protégée ; ne pas cliquer sur ses propres annonces.

Tester sur le domaine approuvé : avant choix, refus, acceptation, retrait, rechargement, mobile et absence de remplissage. L'intégration réelle reste à valider avec le compte et la CMP effectifs. Ce changement ne certifie pas la conformité juridique globale du site.

## Vérifications

`node tests/footer-ad.test.js` teste l'absence de requête sans consentement, le refus, les restrictions, le chargement différé unique, le retrait et l'isolation de la préproduction.

Après construction préproduction : `python3 tests/ad_preview.py` inspecte toutes les pages, y compris les anciennes pages statiques. Les deux contrôles sont intégrés au workflow préproduction.

Références :
- https://support.google.com/adsense/answer/13554116?hl=fr
- https://www.cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies/FAQ
