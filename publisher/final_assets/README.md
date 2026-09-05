# F1 Final Assets

Questa cartella contiene esclusivamente i layout finali gia pronti per la pubblicazione.

Regola vincolante: gli asset presenti qui sono **immutabili**. Il publisher non deve ritagliarli, ridimensionarli, sovrascrivere testi, applicare filtri o ricomporre il layout.

Il flusso e:

AI / layout finale -> `publisher/final_assets/` -> `publisher/final_content_queue.json` -> Cloudinary -> Buffer -> Facebook / Instagram / LinkedIn.

Stati ammessi nella coda: `READY`, `SCHEDULED`, `PUBLISHED`, `ERROR`, `HOLD`.
