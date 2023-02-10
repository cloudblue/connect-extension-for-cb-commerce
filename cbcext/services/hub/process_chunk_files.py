from fastapi.responses import JSONResponse

from cbcext.services.hub.services import (
    close_chunk_file,
    fetch_chunk_files_by_hub_id,
    get_oa_usage_adapter_manager,
    get_usage_chunk_file_content,
    get_usage_files_from_oa,
    update_chunk_file_external_id,
    upload_to_oa,
)


class ProcessUsageChunkFiles:
    """
    Class in charge to cover the usage upload workflow for usage files of type
    TR, CR and PR
    """
    def handle(self, app_id):  # noqa: CCR001
        oa_usage_adapter = get_oa_usage_adapter_manager(app_id)
        if oa_usage_adapter is None:
            return {"message": "Hub does not support automatic usage reporting"}, 200
        chunk_files = fetch_chunk_files_by_hub_id(app_id)
        for chunk_file in chunk_files:
            if str(chunk_file['usagefile']['schema']).lower() == 'qt':
                '''OSA Handles QT Schemas using old pulling way per tenant'''
                continue

            chunk_files_in_oa = get_usage_files_from_oa(
                app_id,
                oa_usage_adapter,
                chunk_file['usagefile']['id'],
                None,
            )
            if len(chunk_files_in_oa) == 0:
                self._upload_and_handle_chunk(chunk_file, oa_usage_adapter, app_id)
            else:
                self._handle_existing_usage_file(chunk_file, oa_usage_adapter, app_id)

        return JSONResponse(content={"message": "OK"}, status_code=200)

    @staticmethod
    def _upload_and_handle_chunk(chunk_file, oa_usage_adapter, app_id):
        """Usage file is not known to OSA, proceeding to download and upload"""
        usage_file_content = get_usage_chunk_file_content(chunk_file['id'])
        """upload to OA """
        uploaded = upload_to_oa(
            app_id,
            oa_usage_adapter,
            chunk_file['id'],
            usage_file_content,
        )
        if not uploaded:
            return
        """Lets search what we uploaded in order to get batch and set it as chunk"""
        processed_reports_in_oa = get_usage_files_from_oa(
            app_id,
            oa_usage_adapter,
            chunk_file['usagefile']['id'],
            'IN_PROGRESS',
        )
        if len(processed_reports_in_oa) == 0:
            """
            Trick in order to solve problem that CB don't supports in operator
            """
            processed_reports_in_oa = get_usage_files_from_oa(
                app_id,
                oa_usage_adapter,
                chunk_file['usagefile']['id'],
                'PROCESSED',
            )
        if len(processed_reports_in_oa) == 1:
            update_chunk_file_external_id(
                chunk_file['id'],
                "Uploaded to commerce automatically, please track result there",
            )

    @staticmethod
    def _handle_existing_usage_file(chunk_file, oa_usage_adapter, app_id):
        """We shall check if by any chance OSA processed file, for any other status we
                        will expect operator to fix using manual procedure"""
        processed_reports_in_oa = get_usage_files_from_oa(
            app_id,
            oa_usage_adapter,
            chunk_file['usagefile']['id'],
            'PROCESSED',
        )
        if len(processed_reports_in_oa) == 1:
            """Let's update the external id"""
            update_chunk_file_external_id(
                chunk_file['id'],
                "hub_batch_{batch_id}".format(
                    batch_id=processed_reports_in_oa[0]['batchId'],
                ),
            )
            """we mark file as processed"""
            close_chunk_file(
                str(chunk_file['id']),
                processed_reports_in_oa[0]['batchId'],
                'Processed in oa by batch {batch_id}'.format(
                    batch_id=processed_reports_in_oa[0]['batchId'],
                ),
            )
