import os

file_path = r"d:\S3K Technology\Apcotex\R&D Backend\R&D Product Recipe Simulator (1)\backend\app\services\pipeline\orchestrator.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "# Preparation phase" in line and i == 666:
        skip = True
        
        new_lines.append("                    # EXTRACTION PHASE (Integrated deterministic & LLM)\n")
        new_lines.append("                    try:\n")
        new_lines.append("                        ext_res = await self.extractor_service.extract_patent(\n")
        new_lines.append("                            parsed_patent=cand._parsed,\n")
        new_lines.append("                            patent_number=cand.publication_number,\n")
        new_lines.append("                            title=cand.title,\n")
        new_lines.append("                            jurisdiction=cand.jurisdiction,\n")
        new_lines.append("                            source_url=cand.url,\n")
        new_lines.append("                            skip_llm=False\n")
        new_lines.append("                        )\n")
        new_lines.append("                        \n")
        new_lines.append("                        if ext_res and ext_res.extraction:\n")
        new_lines.append("                            ext_res.extraction.metadata.publication_year = cand.publication_date\n")
        new_lines.append("                            extractions_by_patent[cand.publication_number] = ext_res.extraction\n")
        new_lines.append("                            extraction_success_count += 1\n")
        new_lines.append("                        else:\n")
        new_lines.append("                            logger.error(f\"Extraction failed (null result) for {cand.publication_number}\")\n")
        new_lines.append("                            \n")
        new_lines.append("                    except Exception as e:\n")
        new_lines.append("                        logger.error(f\"Extraction failed for {cand.publication_number}: {e}\")\n")
        new_lines.append("                        continue\n")
        new_lines.append("                \n")
        new_lines.append("                logger.info(\"=\" * 60)\n")
        new_lines.append("                logger.info(\"PATENT EXTRACTION\")\n")
        new_lines.append("                logger.info(\"=\" * 60)\n")
        new_lines.append("                logger.info(f\"Selected patents: {fetch_attempted}\")\n")
        new_lines.append("                logger.info(f\"Fetched successfully: {fetch_successful}\")\n")
        new_lines.append("                logger.info(f\"Prepared: {fetch_successful}\")\n")
        new_lines.append("                logger.info(f\"Deterministic extraction: {fetch_successful}\")\n")
        new_lines.append(f"                logger.info(f\"LLM extraction successful: {{extraction_success_count}}\")\n")
        new_lines.append(f"                logger.info(f\"LLM extraction failed: {{fetch_successful - extraction_success_count}}\")\n")
        new_lines.append("                logger.info(\"=\" * 60)\n")
        new_lines.append("                \n")
        
    if "COMPETITOR PATENT EXTRACTION (Separate Channel)" in line:
        skip = False
        
    if not skip:
        new_lines.append(line)

with open("scratchpad_orchestrator2.py", 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
