# Client assets (the ONE image door)

Drop image files (png/jpg/jpeg/webp) DIRECTLY into `client_assets/<client_slug>/`
(no subfolders). The live build reads this folder; filenames ARE the routing:

| Filename                | Lands where |
|-------------------------|-------------|
| `founder.png`           | Cover + About founder portrait (unlocks the A3 editorial hero) |
| `team.png`              | About team photo |
| `logo.png`              | About logo |
| `case-study-1.png` (2,3...) | The Nth case study's client portrait (else initials avatar) |
| `proof-1.png` (2,3...)  | Proof gallery |
| `press-logo-1.png` ...  | Press logo wall |
| `client-logo-1.png` ... | Client logo wall |
| `product-1.png` (2,3...) | Product/device shots (PRE-FRAMED laptop/phone/tablet renders). Routed to the pages whose writer `bildwunsch` asked for a device visual, in page order. |

Override the folder location with the env var `DMC_CLIENT_ASSETS_DIR`.
