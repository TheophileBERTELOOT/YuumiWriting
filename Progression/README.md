# Journal de progression

Le véritable journal est créé automatiquement ici sous le nom
`progression.jsonl` lors de la première sauvegarde d'un texte.

Chaque ligne correspond à une journée et contient :

- `date` : la date au format ISO `AAAA-MM-JJ` ;
- `words_written` : les mots ajoutés pendant cette journée ;
- `total_words` : le nombre total de mots du projet ;
- `files` : le dernier nombre de mots connu pour chaque fichier.

Le fichier `exemple_progression.jsonl` est uniquement un exemple. L'application
ne le charge pas et ne le modifie jamais.
