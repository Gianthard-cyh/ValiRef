const DB_NAME = 'ValiRefDB';
const DB_VERSION = 1;
const STORE_NAME = 'pdfs';
const MAX_PDF_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7天
const MAX_PDF_COUNT = 20; // 最多保留20个PDF

interface PDFRecord {
  taskId: string;
  filename: string;
  blob: Blob;
  createdAt: number;
}

let db: IDBDatabase | null = null;

async function initDB(): Promise<IDBDatabase> {
  if (db) return db;

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'taskId' });
        store.createIndex('createdAt', 'createdAt', { unique: false });
      }
    };
  });
}

export async function savePDF(taskId: string, filename: string, file: File): Promise<void> {
  const database = await initDB();

  // 清理旧数据
  await cleanupOldPDFs(database);

  const record: PDFRecord = {
    taskId,
    filename,
    blob: file,
    createdAt: Date.now(),
  };

  return new Promise((resolve, reject) => {
    const transaction = database.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.put(record);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

export async function loadPDF(taskId: string): Promise<File | null> {
  const database = await initDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.get(taskId);

    request.onsuccess = () => {
      const record = request.result as PDFRecord | undefined;
      if (!record) {
        resolve(null);
        return;
      }

      // 检查是否过期
      if (Date.now() - record.createdAt > MAX_PDF_AGE_MS) {
        deletePDF(taskId);
        resolve(null);
        return;
      }

      // 转换为 File 对象
      const file = new File([record.blob], record.filename, {
        type: 'application/pdf',
      });
      resolve(file);
    };

    request.onerror = () => reject(request.error);
  });
}

export async function deletePDF(taskId: string): Promise<void> {
  const database = await initDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.delete(taskId);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function cleanupOldPDFs(database: IDBDatabase): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const index = store.index('createdAt');
    const request = index.openCursor();

    const records: { taskId: string; createdAt: number }[] = [];

    request.onsuccess = () => {
      const cursor = request.result;
      if (cursor) {
        records.push({
          taskId: cursor.value.taskId,
          createdAt: cursor.value.createdAt,
        });
        cursor.continue();
      } else {
        // 清理过期数据
        const now = Date.now();
        const expiredRecords = records.filter(r => now - r.createdAt > MAX_PDF_AGE_MS);

        // 如果超过最大数量，删除最旧的
        let recordsToDelete = expiredRecords.map(r => r.taskId);
        if (records.length - expiredRecords.length > MAX_PDF_COUNT) {
          const sorted = records
            .filter(r => !expiredRecords.includes(r))
            .sort((a, b) => b.createdAt - a.createdAt);
          const toRemove = sorted.slice(MAX_PDF_COUNT);
          recordsToDelete = [...recordsToDelete, ...toRemove.map(r => r.taskId)];
        }

        recordsToDelete.forEach(taskId => {
          store.delete(taskId);
        });

        resolve();
      }
    };

    request.onerror = () => reject(request.error);
  });
}
