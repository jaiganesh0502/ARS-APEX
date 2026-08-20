# Future n8n Workflow Planning Artifacts

## Overview

This directory stores planning/reference material for possible future n8n workflow definitions (`.json` exports). It is not active application behavior.

## Current Architectural Boundary

- FastAPI persists `report_approved` and bed-turnover audit records internally.
- Feature 4 is a manual, authorized workflow: `occupied -> vacating -> cleaning -> available`. The three guarded bed actions are handled by FastAPI and are not driven by n8n, webhooks, or an unrestricted bed-status PATCH route.
- No current workflow sends `report_approved` or bed events to n8n. No n8n workflow may automatically release, clean, or make a bed available.

## Future planning scope

Future, separately approved work may use n8n for transfer matching, ambulance coordination, notifications, or other external workflows. Any future integration must preserve the manual Feature 4 bed-turnover boundary unless its own design and authorization model explicitly changes it.
