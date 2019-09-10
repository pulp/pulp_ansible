import logging

from rq.job import get_current_job


class CollectionImportHandler(logging.Handler):
    """
    A custom Handler which logs into `CollectionImport.messages` attribute of the current task.
    """

    def emit(self, record):
        """
        Log `record` into the `CollectionImport.messages` field of the current task.

        Args:
            record (logging.LogRecord): The record to log.

        """
        # This import cannot occur at import time because Django attempts to instantiate it early
        # which causes an unavoidable circular import as long as this needs to import any model
        from .models import CollectionImport

        collection_import = CollectionImport.objects.get(task=get_current_job().id)
        collection_import.add_log_record(record)
        collection_import.save()
